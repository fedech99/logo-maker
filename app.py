import streamlit as st
from PIL import Image, ImageOps
import os
import tempfile
import time

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Studio Editor", layout="wide")

# --- FUNZIONI UTILI ---
def load_local_logos():
    """Cerca i loghi nella cartella 'logos'"""
    logos = {}
    if os.path.exists("logos"):
        for filename in os.listdir("logos"):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                path = os.path.join("logos", filename)
                try:
                    img = Image.open(path)
                    logos[filename] = img
                except:
                    pass
    return logos

def apply_watermark_photo(base, watermark, position, scale, opacity, margin_px):
    """Logica applicazione logo su FOTO"""
    base_w, base_h = base.size
    
    # Calcolo dimensioni logo
    target_w = int(base_w * (scale / 100))
    aspect = watermark.width / watermark.height
    target_h = int(target_w / aspect)
    
    if target_w < 1 or target_h < 1: return base

    # Resize e Opacità
    wm = watermark.resize((target_w, target_h), Image.Resampling.LANCZOS)
    if wm.mode != 'RGBA': wm = wm.convert('RGBA')
    
    alpha = wm.split()[3]
    alpha = alpha.point(lambda p: p * opacity)
    wm.putalpha(alpha)
    
    # Calcolo Posizione
    margin = int(margin_px)
    if position == "Basso Destra":
        pos = (base_w - target_w - margin, base_h - target_h - margin)
    elif position == "Basso Sinistra":
        pos = (margin, base_h - target_h - margin)
    elif position == "Alto Destra":
        pos = (base_w - target_w - margin, margin)
    elif position == "Alto Sinistra":
        pos = (margin, margin)
    else: # Centro
        pos = ((base_w - target_w)//2, (base_h - target_h)//2)
    
    # Unione
    canvas = Image.new('RGBA', base.size, (0,0,0,0))
    canvas.paste(wm, pos)
    return Image.alpha_composite(base.convert('RGBA'), canvas).convert('RGB')

# --- SIDEBAR: CONTROLLI GLOBALI ---
with st.sidebar:
    st.header("🎛️ Pannello di Controllo")
    
    # 1. Libreria Loghi
    st.subheader("1. Seleziona Logo")
    library_logos = load_local_logos()
    
    # Upload manuale (se non vuoi usare la cartella)
    uploaded_logo = st.file_uploader("Carica logo al volo (opzionale)", type=['png', 'jpg'])
    if uploaded_logo:
        library_logos["Nuovo Caricato"] = Image.open(uploaded_logo)
    
    active_logo = None
    if not library_logos:
        st.warning("⚠️ Nessun logo trovato. Caricane uno o crea la cartella 'logos' su GitHub.")
    else:
        # Menu a tendina per scegliere il logo
        logo_names = list(library_logos.keys())
        selected_name = st.selectbox("Logo attivo:", logo_names)
        active_logo = library_logos[selected_name]
        
        # Anteprima Sidebar
        st.image(active_logo, width=150)
        
        st.divider()
        st.subheader("2. Impostazioni")
        
        scale = st.slider("Grandezza Logo (%)", 5, 80, 20)
        opacity = st.slider("Opacità", 0.1, 1.0, 0.9)
        position = st.selectbox("Posizione", ["Basso Destra", "Basso Sinistra", "Alto Destra", "Alto Sinistra", "Centro"])
        margin = st.slider("Margine (px per foto)", 0, 200, 50)

# --- AREA PRINCIPALE ---
st.title("Studio Content Editor")

tab_foto, tab_video = st.tabs(["📸 FOTO GALLERY", "🎬 VIDEO LAB"])

# === TAB 1: FOTO (BATCH) ===
with tab_foto:
    if not active_logo:
        st.info("👈 Seleziona un logo dalla barra laterale per iniziare.")
    else:
        uploaded_files = st.file_uploader("Carica Foto (anche multiple)", 
                                          accept_multiple_files=True, 
                                          type=['jpg', 'png', 'webp', 'jpeg'])

        if uploaded_files:
            st.write(f"📂 **{len(uploaded_files)} immagini in lavorazione**")
            
            # Opzioni ridimensionamento
            use_resize = st.checkbox("Ridimensiona tutto?")
            if use_resize:
                c1, c2 = st.columns(2)
                w_req = c1.number_input("Larghezza", value=1080)
                h_req = c2.number_input("Altezza", value=1350)
            
            st.divider()
            
            # GRIGLIA ANTEPRIME
            cols = st.columns(3) # 3 colonne
            
            for i, file in enumerate(uploaded_files):
                image = Image.open(file)
                
                # Resize
                if use_resize:
                    image = ImageOps.pad(image, (w_req, h_req), color='white', centering=(0.5, 0.5))
                
                # Apply Logo
                processed = apply_watermark_photo(image, active_logo, position, scale, opacity, margin)
                
                # Visualizzazione
                col_idx = i % 3
                with cols[col_idx]:
                    st.image(processed, use_column_width=True)
                    # Download button
                    import io
                    buf = io.BytesIO()
                    processed.save(buf, format="JPEG", quality=95)
                    st.download_button(f"⬇️ Scarica", data=buf.getvalue(), file_name=f"logo_{file.name}", mime="image/jpeg", key=f"dl_{i}")

# === TAB 2: VIDEO ===
with tab_video:
    st.write("Applicazione logo su video.")
    
    if not active_logo:
        st.warning("👈 Seleziona prima un logo dalla barra laterale.")
    else:
        uploaded_video = st.file_uploader("Carica Video (MP4/MOV)", type=['mp4', 'mov'])
        
        if uploaded_video:
            if st.button("🚀 ELABORA VIDEO"):
                with st.spinner("Rendering video in corso... Potrebbe richiedere qualche minuto."):
                    try:
                        # Importazione ritardata per evitare errori se manca ffmpeg all'avvio
                        from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip
                        
                        # 1. Salva file video temporaneo
                        tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
                        tfile.write(uploaded_video.read())
                        clip = VideoFileClip(tfile.name)
                        
                        # 2. Prepara il Logo per il Video
                        vid_w, vid_h = clip.size
                        logo_w = int(vid_w * (scale / 100))
                        ratio = active_logo.width / active_logo.height
                        logo_h = int(logo_w / ratio)
                        
                        # Resize logo e gestione trasparenza
                        wm_res = active_logo.resize((logo_w, logo_h), Image.Resampling.LANCZOS)
                        if wm_res.mode != 'RGBA': wm_res = wm_res.convert('RGBA')
                        
                        # Opacità
                        alpha = wm_res.split()[3]
                        alpha = alpha.point(lambda p: p * opacity)
                        wm_res.putalpha(alpha)
                        
                        # Salva logo temporaneo su disco (MoviePy lo richiede)
                        logo_path = tempfile.mktemp(suffix=".png")
                        wm_res.save(logo_path)
                        
                        # 3. Mappa Posizione (Da testo a coordinate MoviePy)
                        # MoviePy usa stringhe in inglese o coordinate
                        pos_map = {
                            "Basso Destra": ("right", "bottom"),
                            "Basso Sinistra": ("left", "bottom"),
                            "Alto Destra": ("right", "top"),
                            "Alto Sinistra": ("left", "top"),
                            "Centro": ("center", "center")
                        }
                        
                        # 4. Crea Clip Logo
                        watermark_clip = (ImageClip(logo_path)
                                          .set_duration(clip.duration)
                                          .set_pos(pos_map[position])
                                          .set_opacity(opacity))
                        
                        # 5. Composizione Finale
                        final = CompositeVideoClip([clip, watermark_clip])
                        
                        # 6. Scrittura File Output
                        output_path = tempfile.mktemp(suffix=".mp4")
                        # Usa preset ultrafast per non sovraccaricare il server
                        final.write_videofile(output_path, codec="libx264", preset="ultrafast", 
                                            audio_codec="aac", temp_audiofile='temp-audio.m4a', 
                                            remove_temp=True, verbose=False, logger=None)
                        
                        st.success("Video Completato!")
                        st.video(output_path)
                        
                        with open(output_path, "rb") as f:
                            st.download_button("💾 SALVA VIDEO", f, "video_logo.mp4", "video/mp4")
                            
                    except Exception as e:
                        st.error(f"Errore durante l'elaborazione video: {e}")
                        st.info("Suggerimento: Se leggi un errore su 'ffmpeg', assicurati che il file 'packages.txt' esista su GitHub.")
