import streamlit as st
from PIL import Image
import os
import tempfile
import zipfile
import io

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Logo Applicator", layout="wide")

st.markdown("""
<style>
    .stButton>button {
        width: 100%; 
        border-radius: 12px; 
        height: 3.5em; 
        font-weight: bold;
        font-size: 18px;
    }
    div[data-testid="stFileUploader"] section {background-color: #f7f9fc;}
</style>
""", unsafe_allow_html=True)

# --- FUNZIONI ---

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

def calculate_position(W, H, w, h, pos_name, margin):
    """
    Funzione matematica che calcola X e Y basandosi sul margine.
    W, H = Dimensioni Sfondo
    w, h = Dimensioni Logo
    """
    m = int(margin)
    x, y = 0, 0
    
    if pos_name == "Basso Destra":
        x = W - w - m
        y = H - h - m
    elif pos_name == "Basso Sinistra":
        x = m
        y = H - h - m
    elif pos_name == "Alto Destra":
        x = W - w - m
        y = m
    elif pos_name == "Alto Sinistra":
        x = m
        y = m
    else: # Centro
        x = (W - w) // 2
        y = (H - h) // 2
        
    return (x, y)

def process_image(image, logo, pos_name, scale, opacity, margin):
    """Elaborazione FOTO"""
    if image.width > 2500 or image.height > 2500:
        image.thumbnail((2500, 2500), Image.Resampling.LANCZOS)
        
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
    
    # Calcolo Posizione usando la funzione comune
    x, y = calculate_position(base_w, base_h, target_w, target_h, pos_name, margin)
    
    canvas = Image.new('RGBA', image.size, (0,0,0,0))
    canvas.paste(wm, (x, y))
    return Image.alpha_composite(image.convert('RGBA'), canvas).convert('RGB')

def process_video_pixel_perfect(tfile_path, logo, pos_name, scale, opacity, margin):
    """
    Versione VIDEO con MARGINE REALE.
    """
    from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip
    
    clip = VideoFileClip(tfile_path)
    W, H = clip.size 
    
    # Logo Setup
    logo_w = int(W * (scale / 100))
    ratio = logo.width / logo.height
    logo_h = int(logo_w / ratio)
    
    pil_logo = logo.resize((logo_w, logo_h), Image.Resampling.LANCZOS)
    if pil_logo.mode != 'RGBA': pil_logo = pil_logo.convert('RGBA')
    
    alpha = pil_logo.split()[3]
    alpha = alpha.point(lambda p: p * opacity)
    pil_logo.putalpha(alpha)
    
    logo_path = tempfile.mktemp(suffix=".png")
    pil_logo.save(logo_path)
    
    # --- QUI STA LA MAGIA ---
    # Invece di dire "bottom", calcoliamo i pixel esatti col margine
    pos_coords = calculate_position(W, H, logo_w, logo_h, pos_name, margin)
    
    # Se è "Centro", MoviePy preferisce la stringa, altrimenti usiamo le coordinate
    if pos_name == "Centro":
        final_pos = ("center", "center")
    else:
        final_pos = pos_coords

    watermark = (ImageClip(logo_path)
                 .set_duration(clip.duration)
                 .set_pos(final_pos) 
                 .set_opacity(opacity))
    
    final = CompositeVideoClip([clip, watermark], size=(W, H))
    
    out_path = tempfile.mktemp(suffix=".mp4")
    final.write_videofile(out_path, codec="libx264", audio_codec="aac", preset="medium", fps=clip.fps, remove_temp=True, verbose=False, logger=None)
    
    return out_path

# --- INTERFACCIA ---
with st.sidebar:
    st.header("🎛️ CONTROLLI")
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
        scale = st.slider("Grandezza %", 5, 80, 20)
        opacity = st.slider("Opacità", 0.1, 1.0, 0.9)
        position = st.selectbox("Posizione", ["Basso Destra", "Basso Sinistra", "Alto Destra", "Alto Sinistra", "Centro"])
        
        # ORA FUNZIONA PER TUTTI
        margin = st.slider("Margine dai bordi (Pixel)", 0, 300, 50) 

# --- MAIN ---
st.title("📂 Media Editor (Pixel Perfect & Margini)")

if active_logo:
    with st.form("main_form"):
        files = st.file_uploader("Carica file", accept_multiple_files=True)
        submitted = st.form_submit_button("⚡ ELABORA")

    if submitted and files:
        images = [f for f in files if f.type.startswith('image')]
        videos = [f for f in files if f.type.startswith('video')]
        
        proc_imgs = []
        proc_vids = []
        
        prog = st.progress(0)
        total_steps = len(images) + (len(videos) * 3)
        curr_step = 0
        
        # FOTO
        if images:
            st.subheader(f"🖼️ Foto ({len(images)})")
            cols = st.columns(3)
            for i, f in enumerate(images):
                res = process_image(Image.open(f), active_logo, position, scale, opacity, margin)
                buf = io.BytesIO()
                res.save(buf, format='JPEG', quality=95)
                proc_imgs.append((f"logo_{f.name}", buf.getvalue()))
                
                with cols[i % 3]:
                    st.image(res, use_column_width=True)
                
                curr_step += 1
                prog.progress(min(curr_step/total_steps, 1.0))
                
        # VIDEO
        if videos:
            st.divider()
            st.subheader(f"🎬 Video ({len(videos)})")
            for v in videos:
                st.info(f"Video: {v.name}...")
                tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
                tfile.write(v.read())
                
                try:
                    # Passiamo il margine anche qui!
                    out = process_video_pixel_perfect(tfile.name, active_logo, position, scale, opacity, margin)
                    with open(out, "rb") as f:
                        proc_vids.append((f"logo_{v.name}", f.read()))
                    st.video(out)
                except Exception as e:
                    st.error(f"Errore {v.name}: {e}")
                
                curr_step += 3
                prog.progress(min(curr_step/total_steps, 1.0))

        # ZIP
        if proc_imgs or proc_vids:
            st.success("Fatto!")
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for name, data in proc_imgs: zf.writestr(name, data)
                for name, data in proc_vids: zf.writestr(name, data)
            
            st.download_button("📦 SCARICA ZIP", zip_buffer.getvalue(), "media_completi.zip", "application/zip", type="primary")
