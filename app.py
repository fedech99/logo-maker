import streamlit as st
from PIL import Image, ImageOps
import os
import tempfile
import zipfile
import io
import time

# --- 1. CONFIGURAZIONE PAGINA E CSS MOBILE ---
st.set_page_config(page_title="Editor Pro Mobile", layout="wide")

st.markdown("""
<style>
    /* Ottimizzazione Touch/Mobile */
    .stButton>button {
        width: 100%; 
        border-radius: 12px; 
        height: 3.5em; 
        font-weight: bold;
        font-size: 18px;
    }
    
    /* Spazio per evitare che la navbar copra il titolo su mobile */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 5rem;
    }
    
    /* Box upload più evidente */
    div[data-testid="stFileUploader"] section {
        background-color: #f0f2f6;
        border: 2px dashed #a1a1a1;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. FUNZIONI DI ELABORAZIONE ---

def load_local_logos():
    """Cerca i loghi nella cartella 'logos' su GitHub"""
    logos = {}
    if os.path.exists("logos"):
        for filename in os.listdir("logos"):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                try:
                    path = os.path.join("logos", filename)
                    img = Image.open(path)
                    logos[filename] = img
                except: pass
    return logos

def process_image(image, logo, pos, scale, opacity, margin):
    """Applica logo su Foto"""
    # Ridimensionamento intelligente
    base_w, base_h = image.size
    target_w = int(base_w * (scale / 100))
    aspect = logo.width / logo.height
    target_h = int(target_w / aspect)
    
    if target_w < 1: return image

    # Preparazione Logo
    wm = logo.resize((target_w, target_h), Image.Resampling.LANCZOS)
    if wm.mode != 'RGBA': wm = wm.convert('RGBA')
    
    # Opacità
    alpha = wm.split()[3]
    alpha = alpha.point(lambda p: p * opacity)
    wm.putalpha(alpha)
    
    # Posizione
    m = int(margin)
    if pos == "Basso Destra": p = (base_w - target_w - m, base_h - target_h - m)
    elif pos == "Basso Sinistra": p = (m, base_h - target_h - m)
    elif pos == "Alto Destra": p = (base_w - target_w - m, m)
    elif pos == "Alto Sinistra": p = (m, m)
    else: p = ((base_w - target_w)//2, (base_h - target_h)//2)
    
    # Unione
    canvas = Image.new('RGBA', image.size, (0,0,0,0))
    canvas.paste(wm, p)
    return Image.alpha_composite(image.convert('RGBA'), canvas).convert('RGB')

def process_video(tfile_path, logo, pos, scale, opacity):
    """Applica logo su Video usando MoviePy"""
    # Importiamo qui per evitare crash se manca la libreria all'avvio
    from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip
    
    clip = VideoFileClip(tfile_path)
    vid_w, vid_h = clip.size
    
    # Preparazione Logo Video
    logo_w = int(vid_w * (scale / 100))
    ratio = logo.width / logo.height
    logo_h = int(logo_w / ratio)
    
    wm_res = logo.resize((logo_w, logo_h), Image.Resampling.LANCZOS)
    if wm_res.mode != 'RGBA': wm_res = wm_res.convert('RGBA')
    wm_res.putalpha(wm_res.split()[3].point(lambda p: p * opacity))
    
    # Salva logo temporaneo
    wm_path = tempfile.mktemp(suffix=".png")
    wm_res.save(wm_path)
    
    # Mappatura posizioni per MoviePy
    pos_map = {
        "Basso Destra": ("right", "bottom"), "Basso Sinistra": ("left", "bottom"),
        "Alto Destra": ("right", "top"), "Alto Sinistra": ("left", "top"),
        "Centro": ("center", "center")
    }
    
    # Creazione Clip
    watermark = (ImageClip(wm_path)
                 .set_duration(clip.duration)
                 .set_pos(pos_map[pos])
                 .set_opacity(opacity))
                 
    final = CompositeVideoClip([clip, watermark])
    
    # Output file
    out_path = tempfile.mktemp(suffix=".mp4")
    # Preset 'ultrafast' è fondamentale per la velocità su server cloud
    final.write_videofile(out_path, codec="libx264", preset="ultrafast", audio_codec="aac", remove_temp=True, verbose=False, logger=None)
    return out_path

# --- 3. INTERFACCIA LATERALE (SIDEBAR) ---
with st.sidebar:
    st.header("🎛️ IMPOSTAZIONI")
    
    # Caricamento Loghi
    library_logos = load_local_logos()
    
    # Se non ci sono loghi nella cartella, permetti upload
    if not library_logos:
        st.warning("Cartella 'logos' vuota.")
        uploaded_logo = st.file_uploader("Carica un logo ora", type=['png'])
        if uploaded_logo: library_logos["Temp"] = Image.open(uploaded_logo)
    
    active_logo = None
    
    if library_logos:
        s_name = st.selectbox("Scegli Logo:", list(library_logos.keys()))
        active_logo = library_logos[s_name]
        st.image(active_logo, width=150)
        
        st.divider()
        st.subheader("Regolazioni")
        scale = st.slider("Grandezza %", 5, 80, 20)
        opacity = st.slider("Opacità", 0.1, 1.0, 0.9)
        position = st.selectbox("Posizione", ["Basso Destra", "Basso Sinistra", "Alto Destra", "Alto Sinistra", "Centro"])
        margin = st.slider("Margine (Pixel)", 0, 200, 50)
    else:
        st.error("Carica un logo per iniziare!")

# --- 4. INTERFACCIA PRINCIPALE ---
st.title("📂 Media Editor All-in-One")

if active_logo:
    # AREA UPLOAD UNICA
    files = st.file_uploader("Trascina qui FOTO e VIDEO insieme", 
                             accept_multiple_files=True, 
                             type=['jpg', 'jpeg', 'png', 'webp', 'mp4', 'mov'])

    if files:
        # Separiamo foto e video
        images = [f for f in files if f.type.startswith('image')]
        videos = [f for f in files if f.type.startswith('video')]
        
        st.info(f"Rilevati: {len(images)} Foto | {len(videos)} Video")
        
        # Variabili per gestire il download finale
        processed_images = []
        processed_videos = []
        
        # --- A. ELABORAZIONE FOTO (Automatica) ---
        if images:
            st.subheader("🖼️ Anteprima Foto")
            cols = st.columns(3) # Griglia
            
            for i, file in enumerate(images):
                img = Image.open(file)
                # Processa
                res = process_image(img, active_logo, position, scale, opacity, margin)
                
                # Salva in memoria per dopo
                img_byte_arr = io.BytesIO()
                res.save(img_byte_arr, format='JPEG', quality=95)
                processed_images.append((f"edited_{file.name}", img_byte_arr.getvalue()))
                
                # Mostra anteprima
                with cols[i % 3]:
                    st.image(res, use_column_width=True)

        # --- B. ELABORAZIONE VIDEO (Su richiesta) ---
        if videos:
            st.divider()
            st.subheader("🎬 Video")
            
            run_video = st.checkbox("Clicca qui per elaborare anche i video (richiede tempo)", value=False)
            
            if run_video:
                prog_bar = st.progress(0)
                for i, v_file in enumerate(videos):
                    st.write(f"Rendering: {v_file.name}...")
                    
                    # Salva temp input
                    tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
                    tfile.write(v_file.read())
                    
                    try:
                        # Processa
                        out_path = process_video(tfile.name, active_logo, position, scale, opacity)
                        
                        # Leggi il file elaborato per il download
                        with open(out_path, "rb") as f:
                            video_bytes = f.read()
                            processed_videos.append((f"edited_{v_file.name}", video_bytes))
                        
                        st.video(out_path)
                        
                    except Exception as e:
                        st.error(f"Errore su {v_file.name}: {e}")
                    
                    prog_bar.progress((i + 1) / len(videos))

        # --- C. GENERAZIONE ZIP FINALE ---
        # Creiamo lo ZIP solo se c'è qualcosa di pronto
        total_items = len(processed_images) + len(processed_videos)
        
        if total_items > 0:
            st.divider()
            st.success("✅ Elaborazione completata!")
            
            # Creazione ZIP in memoria
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                # Aggiungi foto
                for name, data in processed_images:
                    zf.writestr(name, data)
                # Aggiungi video
                for name, data in processed_videos:
                    zf.writestr(name, data)
            
            # TASTO DOWNLOAD UNICO
            st.download_button(
                label=f"📦 SCARICA TUTTO ({total_items} file)",
                data=zip_buffer.getvalue(),
                file_name="media_con_logo.zip",
                mime="application/zip",
                type="primary"
            )
            st.caption("Su iPhone/Android: Dopo il download, clicca 'Condividi' per inviare via WeTransfer o Whatsapp.")

else:
    st.info("👈 Apri il menu laterale (in alto a sinistra su mobile) per selezionare un logo.")
