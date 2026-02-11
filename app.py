import streamlit as st
from PIL import Image, ImageOps
import os
import tempfile
import zipfile
import io

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Universal Batch Editor", layout="wide")

# --- CSS CUSTOM ---
st.markdown("""
<style>
    .stButton>button {width: 100%; border-radius: 5px;}
    div[data-testid="stFileUploader"] {text-align: center;}
</style>
""", unsafe_allow_html=True)

# --- FUNZIONI UTILI ---
def load_local_logos():
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
    # Logica ridimensionamento e logo
    base_w, base_h = image.size
    target_w = int(base_w * (scale / 100))
    aspect = logo.width / logo.height
    target_h = int(target_w / aspect)
    
    if target_w < 1: return image

    wm = logo.resize((target_w, target_h), Image.Resampling.LANCZOS)
    if wm.mode != 'RGBA': wm = wm.convert('RGBA')
    
    alpha = wm.split()[3]
    alpha = alpha.point(lambda p: p * opacity)
    wm.putalpha(alpha)
    
    m = int(margin)
    if pos == "Basso Destra": p = (base_w - target_w - m, base_h - target_h - m)
    elif pos == "Basso Sinistra": p = (m, base_h - target_h - m)
    elif pos == "Alto Destra": p = (base_w - target_w - m, m)
    elif pos == "Alto Sinistra": p = (m, m)
    else: p = ((base_w - target_w)//2, (base_h - target_h)//2)
    
    canvas = Image.new('RGBA', image.size, (0,0,0,0))
    canvas.paste(wm, p)
    return Image.alpha_composite(image.convert('RGBA'), canvas).convert('RGB')

def process_video(tfile_path, logo, pos, scale, opacity):
    from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip
    
    clip = VideoFileClip(tfile_path)
    vid_w, vid_h = clip.size
    
    # Preparazione Logo
    logo_w = int(vid_w * (scale / 100))
    ratio = logo.width / logo.height
    logo_h = int(logo_w / ratio)
    
    wm_res = logo.resize((logo_w, logo_h), Image.Resampling.LANCZOS)
    if wm_res.mode != 'RGBA': wm_res = wm_res.convert('RGBA')
    wm_res.putalpha(wm_res.split()[3].point(lambda p: p * opacity))
    
    wm_path = tempfile.mktemp(suffix=".png")
    wm_res.save(wm_path)
    
    pos_map = {
        "Basso Destra": ("right", "bottom"), "Basso Sinistra": ("left", "bottom"),
        "Alto Destra": ("right", "top"), "Alto Sinistra": ("left", "top"),
        "Centro": ("center", "center")
    }
    
    watermark = (ImageClip(wm_path)
                 .set_duration(clip.duration)
                 .set_pos(pos_map[pos])
                 .set_opacity(opacity))
                 
    final = CompositeVideoClip([clip, watermark])
    out_path = tempfile.mktemp(suffix=".mp4")
    final.write_videofile(out_path, codec="libx264", preset="ultrafast", audio_codec="aac", remove_temp=True, verbose=False, logger=None)
    return out_path

# --- SIDEBAR ---
with st.sidebar:
    st.header("🎛️ Controlli")
    library_logos = load_local_logos()
    
    if not library_logos:
        st.warning("Nessun logo in 'logos'. Caricane uno qui sotto.")
        uploaded_logo = st.file_uploader("Carica Logo", type=['png'])
        if uploaded_logo: library_logos["Temp"] = Image.open(uploaded_logo)
    
    active_logo = None
    if library_logos:
        s_name = st.selectbox("Logo:", list(library_logos.keys()))
        active_logo = library_logos[s_name]
        st.image(active_logo, width=120)
        
        st.divider()
        scale = st.slider("Grandezza %", 5, 80, 20)
        opacity = st.slider("Opacità", 0.1, 1.0, 0.9)
        position = st.selectbox("Posizione", ["Basso Destra", "Basso Sinistra", "Alto Destra", "Alto Sinistra", "Centro"])
        margin = st.slider("Margine (px)", 0, 200, 50)

# --- MAIN ---
st.title("📂 Media Processor All-in-One")

if not active_logo:
    st.info("👈 Seleziona prima un logo.")
else:
    # UPLOAD UNIFICATO
    files = st.file_uploader("Trascina qui FOTO e VIDEO insieme", 
                             accept_multiple_files=True, 
                             type=['jpg', 'jpeg', 'png', 'webp', 'mp4', 'mov'])

    if files:
        # Separiamo i file
        images = [f for f in files if f.type.startswith('image')]
        videos = [f for f in files if f.type.startswith('video')]
        
        st.write(f"📊 Rilevati: **{len(images)} Foto** | **{len(videos)} Video**")
        
        # Buffer per lo ZIP finale
        zip_buffer = io.BytesIO()
        processed_count = 0
        
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            
            # 1. ELABORAZIONE FOTO (Automatica)
            if images:
                st.subheader("🖼️ Foto Elaborate")
                cols = st.columns(3)
                
                for i, file in enumerate(images):
                    img = Image.open(file)
                    # Elabora
                    res = process_image(img, active_logo, position, scale, opacity, margin)
                    
                    # Mostra
                    with cols[i % 3]:
                        st.image(res, use_column_width=True)
                    
                    # Salva nello ZIP
                    img_byte_arr = io.BytesIO()
                    res.save(img_byte_arr, format='JPEG', quality=95)
                    zip_file.writestr(f"edited_{file.name}", img_byte_arr.getvalue())
                    processed_count += 1

            # 2. ELABORAZIONE VIDEO (Manuale o Automatica)
            if videos:
                st.divider()
                st.subheader("🎬 Video (Richiedono elaborazione)")
                
                # Checkbox per sicurezza performance
                if st.checkbox("Elabora anche i video ora? (Potrebbe richiedere tempo)", value=False):
                    progress_bar = st.progress(0)
                    
                    for i, v_file in enumerate(videos):
                        st.write(f"Rendering: {v_file.name}...")
                        
                        # Salva temp
                        tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
                        tfile.write(v_file.read())
                        
                        try:
                            # Elabora
                            out_path = process_video(tfile.name, active_logo, position, scale, opacity)
                            
                            # Aggiungi allo ZIP
                            zip_file.write(out_path, f"edited_{v_file.name}")
                            st.video(out_path) # Mostra anteprima
                            processed_count += 1
                            
                        except Exception as e:
                            st.error(f"Errore su {v_file.name}: {e}")
                            
                        progress_bar.progress((i + 1) / len(videos))
                        
                else:
                    st.info("Spunta la casella qui sopra per avviare il rendering dei video.")

        # --- TASTO SCARICA TUTTO ---
        if processed_count > 0:
            st.divider()
            st.success("Tutti i file elaborati sono pronti!")
            st.download_button(
                label="📦 SCARICA TUTTO (ZIP)",
                data=zip_buffer.getvalue(),
                file_name="media_con_logo.zip",
                mime="application/zip",
                type="primary"
            )
