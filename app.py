import streamlit as st
from PIL import Image, ImageOps
import os
import tempfile
import zipfile
import io
import time

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Editor Logo Pro", layout="wide")

st.markdown("""
<style>
    /* Ottimizzazione Mobile */
    .stButton>button {
        width: 100%; 
        border-radius: 12px; 
        height: 3.5em; 
        font-weight: bold;
        font-size: 18px;
    }
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 5rem;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. FUNZIONI ---

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

def smart_resize_for_mobile(img):
    """Solo per le FOTO: riduce se enormi per evitare crash"""
    max_dim = 2500
    if img.width > max_dim or img.height > max_dim:
        img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
    return img

def process_image(image, logo, pos, scale, opacity, margin):
    # FOTO: Riduzione sicurezza + Logo
    image = smart_resize_for_mobile(image)
    base_w, base_h = image.size
    
    # Calcolo Logo
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

def process_video_strict(tfile_path, logo, pos, scale, opacity, rotate_fix):
    """
    Versione Strict: Mantiene risoluzione e FPS originali al 100%.
    """
    from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip
    
    # Carica video
    clip = VideoFileClip(tfile_path)
    
    # ROTAZIONE MANUALE (Solo se richiesto)
    if rotate_fix:
        clip = clip.rotate(-90)

    # --- RISOLUZIONE ORIGINALE ---
    # Non ridimensioniamo NULLA. Usiamo w e h originali.
    final_w = clip.w
    final_h = clip.h

    # FIX PIXEL DISPARI (Obbligatorio per MP4/H.264)
    # Rimuove max 1 pixel se le dimensioni sono dispari (invisibile all'occhio)
    if final_w % 2 != 0: final_w -= 1
    if final_h % 2 != 0: final_h -= 1
    
    # Se abbiamo dovuto correggere i pixel dispari, tagliamo impercettibilmente
    if final_w != clip.w or final_h != clip.h:
        clip = clip.crop(x1=0, y1=0, width=final_w, height=final_h)

    # Preparazione Logo su dimensioni originali
    logo_w = int(final_w * (scale / 100))
    ratio = logo.width / logo.height
    logo_h = int(logo_w / ratio)
    
    wm_res = logo.resize((logo_w, logo_h), Image.Resampling.LANCZOS)
    if wm_res.mode != 'RGBA': wm_res = wm_res.convert('RGBA')
    wm_res.putalpha(wm_res.split()[3].point(lambda p: p * opacity))
    
    wm_path = tempfile.mktemp(suffix=".png")
    wm_res.save(wm_path)
    
    # Posizionamento
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
    
    # SALVATAGGIO CON PARAMETRI ORIGINALI
    # preset='medium' per qualità bilanciata, fps originali del clip
    final.write_videofile(out_path, 
                          codec="libx264", 
                          preset="medium", 
                          audio_codec="aac", 
                          fps=clip.fps,  # Mantiene i 30/60 fps originali
                          remove_temp=True, 
                          verbose=False, 
                          logger=None)
    
    return out_path

# --- 3. INTERFACCIA ---
with st.sidebar:
    st.header("🎛️ IMPOSTAZIONI")
    library_logos = load_local_logos()
    
    if not library_logos:
        st.warning("Cartella 'logos' vuota.")
        uploaded_logo = st.file_uploader("Carica logo", type=['png'])
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
        margin = st.slider("Margine", 0, 200, 50)
        
        st.divider()
        st.caption("🔧 Opzioni Video")
        rotate_fix = st.checkbox("Ruota video 90° (Se esce storto)")

# --- 4. MAIN ---
st.title("📂 Logo Applicator (Formato Originale)")

if active_logo:
    with st.form("my-form", clear_on_submit=False):
        files = st.file_uploader("Trascina qui FOTO e VIDEO insieme", 
                                accept_multiple_files=True, 
                                type=['jpg', 'jpeg', 'png', 'webp', 'mp4', 'mov'])
        
        submitted = st.form_submit_button("⚡ ELABORA ORA")

    if submitted and files:
        images = [f for f in files if f.type.startswith('image')]
        videos = [f for f in files if f.type.startswith('video')]
        
        processed_images = []
        processed_videos = []
        
        # BARRA DI CARICAMENTO
        total_steps = len(images) + (len(videos) * 3)
        progress_bar = st.progress(0)
        current_step = 0
        
        # FOTO
        if images:
            st.subheader("🖼️ Foto")
            cols = st.columns(3)
            for i, file in enumerate(images):
                img = Image.open(file)
                res = process_image(img, active_logo, position, scale, opacity, margin)
                
                img_byte_arr = io.BytesIO()
                res.save(img_byte_arr, format='JPEG', quality=95)
                processed_images.append((f"logo_{file.name}", img_byte_arr.getvalue()))
                
                with cols[i % 3]:
                    st.image(res, use_column_width=True)
                
                current_step += 1
                progress_bar.progress(min(current_step / total_steps, 1.0))

        # VIDEO
        if videos:
            st.divider()
            st.subheader("🎬 Video")
            for i, v_file in enumerate(videos):
                st.info(f"Rendering: {v_file.name} (Formato Originale)...")
                tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
                tfile.write(v_file.read())
                
                try:
                    out_path = process_video_strict(tfile.name, active_logo, position, scale, opacity, rotate_fix)
                    
                    with open(out_path, "rb") as f:
                        processed_videos.append((f"logo_{v_file.name}", f.read()))
                    
                    # NOTA BENE: Il player di Streamlit potrebbe MOSTRARE il video con bande nere
                    # ma il file scaricato sarà corretto.
                    st.video(out_path)
                    st.caption("⚠️ Se l'anteprima qui sopra sembra avere bande nere, ignorala. Scarica il file: sarà corretto (4:3 o originale).")
                    
                except Exception as e:
                    st.error(f"Errore: {e}")
                
                current_step += 3
                progress_bar.progress(min(current_step / total_steps, 1.0))

        # ZIP FINALE
        if processed_images or processed_videos:
            st.divider()
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for name, data in processed_images: zf.writestr(name, data)
                for name, data in processed_videos: zf.writestr(name, data)
            
            st.success("✅ Fatto!")
            st.download_button(
                label="📦 SCARICA ZIP TOTALE",
                data=zip_buffer.getvalue(),
                file_name="media_completi.zip",
                mime="application/zip",
                type="primary"
            )

else:
    st.info("👈 Scegli un logo dal menu laterale.")
