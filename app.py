import streamlit as st
from PIL import Image, ImageOps
import tempfile
import os

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Editor Foto & Video", layout="centered")
st.title("🎨 Editor Foto & Video Pro")

# --- FUNZIONI UTILI ---
def resize_image(image, width, height):
    """Ridimensiona l'immagine aggiungendo bordi (pad) per non tagliare nulla."""
    return ImageOps.pad(image, (width, height), color='white', centering=(0.5, 0.5))

def apply_watermark(base, watermark, position, scale, opacity):
    """Applica il logo sulla base (foto o frame video)."""
    # 1. Calcola dimensioni logo
    base_w, base_h = base.size
    logo_w = int(base_w * (scale / 100))
    aspect_ratio = watermark.width / watermark.height
    logo_h = int(logo_w / aspect_ratio)
    
    # Evita errori se il logo diventa piccolissimo
    if logo_w < 1 or logo_h < 1:
        return base

    # 2. Ridimensiona Logo
    wm = watermark.resize((logo_w, logo_h), Image.Resampling.LANCZOS)
    
    # 3. Applica Opacità
    if wm.mode != 'RGBA':
        wm = wm.convert('RGBA')
    
    # Crea una nuova immagine per l'opacità
    alpha = wm.split()[3]
    alpha = alpha.point(lambda p: p * opacity)
    wm.putalpha(alpha)
    
    # 4. Calcola Posizione
    padding = int(base_w * 0.05) # 5% di margine
    
    if position == "Basso Destra":
        pos = (base_w - logo_w - padding, base_h - logo_h - padding)
    elif position == "Basso Sinistra":
        pos = (padding, base_h - logo_h - padding)
    elif position == "Alto Destra":
        pos = (base_w - logo_w - padding, padding)
    elif position == "Alto Sinistra":
        pos = (padding, padding)
    else: # Centro
        pos = ((base_w - logo_w) // 2, (base_h - logo_h) // 2)
        
    # 5. Incolla
    # Creiamo una copia trasparente grande come la base per fare il merge
    layer = Image.new('RGBA', base.size, (0,0,0,0))
    layer.paste(wm, pos)
    
    return Image.alpha_composite(base.convert('RGBA'), layer).convert('RGB')

# --- SIDEBAR: LOGO ---
st.sidebar.header("1. Carica il Logo")
logo_file = st.sidebar.file_uploader("Scegli il file PNG del logo", type=['png', 'jpg'])

logo_img = None
if logo_file:
    logo_img = Image.open(logo_file)
    st.sidebar.image(logo_img, width=150, caption="Anteprima Logo")
    st.sidebar.divider()
    st.sidebar.subheader("Regolazioni Logo")
    opacity = st.sidebar.slider("Opacità", 0.1, 1.0, 0.9)
    scale = st.sidebar.slider("Grandezza (%)", 5, 80, 20)
    position = st.sidebar.selectbox("Posizione", 
        ["Basso Destra", "Basso Sinistra", "Alto Destra", "Alto Sinistra", "Centro"])
else:
    st.sidebar.warning("⚠️ Carica prima il logo!")

# --- TABS PRINCIPALI ---
tab1, tab2 = st.tabs(["📸 FOTO", "🎬 VIDEO"])

# === TAB FOTO ===
with tab1:
    st.header("Modifica Foto")
    uploaded_photo = st.file_uploader("Carica foto", type=['jpg', 'jpeg', 'png', 'webp'])
    
    if uploaded_photo and logo_img:
        image = Image.open(uploaded_photo)
        
        st.subheader("Ridimensionamento (Pixel)")
        col1, col2 = st.columns(2)
        with col1:
            target_w = st.number_input("Larghezza (W)", value=1080, step=1)
        with col2:
            target_h = st.number_input("Altezza (H)", value=1350, step=1) # Default portrait
            
        # Pulsante anteprima
        base_resized = resize_image(image, target_w, target_h)
        
        # Applicazione Logo
        final_image = apply_watermark(base_resized, logo_img, position, scale, opacity)
        
        st.image(final_image, caption="Anteprima Risultato")
        
        # Download
        import io
        buf = io.BytesIO()
        final_image.save(buf, format="JPEG", quality=100)
        st.download_button("⬇️ Scarica Foto", data=buf.getvalue(), file_name="foto_editata.jpg", mime="image/jpeg")

# === TAB VIDEO ===
with tab2:
    st.header("Modifica Video")
    uploaded_video = st.file_uploader("Carica video (MP4/MOV)", type=['mp4', 'mov'])
    
    if uploaded_video and logo_img:
        st.info("💡 I video richiedono tempo. Attendi la fine dell'elaborazione.")
        
        if st.button("🎬 Elabora Video"):
            with st.spinner("Sto lavorando sul video... non chiudere la pagina..."):
                try:
                    # Importa qui per evitare errori se la libreria manca
                    from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip
                    
                    # Salva video temporaneo
                    tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
                    tfile.write(uploaded_video.read())
                    
                    # Carica clip
                    clip = VideoFileClip(tfile.name)
                    
                    # --- PREPARAZIONE LOGO PER VIDEO ---
                    # Calcoliamo le dimensioni in pixel basandoci sul video
                    vid_w, vid_h = clip.size
                    logo_target_w = int(vid_w * (scale / 100))
                    ar = logo_img.width / logo_img.height
                    logo_target_h = int(logo_target_w / ar)
                    
                    # Ridimensiona logo con PIL
                    wm_resized = logo_img.resize((logo_target_w, logo_target_h), Image.Resampling.LANCZOS)
                    # Applica opacità
                    wm_resized.putalpha(wm_resized.split()[3].point(lambda p: p * opacity))
                    
                    # Salva logo temporaneo per MoviePy
                    logo_temp_path = tempfile.mktemp(suffix=".png")
                    wm_resized.save(logo_temp_path)
                    
                    # Crea clip logo
                    watermark_clip = (ImageClip(logo_temp_path)
                                      .set_duration(clip.duration)
                                      .set_pos(position.lower().replace(" ", "_").replace("basso", "bottom").replace("alto", "top").replace("destra", "right").replace("sinistra", "left")))
                                      
                    # Se posizionamento automatico non piace, usiamo coordinate relative
                    # (Qui uso la logica semplificata di moviepy 'bottom', 'right' ecc)
                    
                    # Composizione
                    final = CompositeVideoClip([clip, watermark_clip])
                    
                    # Output
                    output_path = tempfile.mktemp(suffix=".mp4")
                    final.write_videofile(output_path, codec="libx264", audio_codec="aac", temp_audiofile='temp-audio.m4a', remove_temp=True, verbose=False, logger=None)
                    
                    # Mostra e Scarica
                    st.success("Fatto!")
                    st.video(output_path)
                    
                    with open(output_path, "rb") as file:
                        btn = st.download_button(
                            label="⬇️ Scarica Video",
                            data=file,
                            file_name="video_con_logo.mp4",
                            mime="video/mp4"
                        )
                        
                except Exception as e:
                    st.error(f"Errore: {e}")
