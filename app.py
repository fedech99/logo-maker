import streamlit as st
from PIL import Image, ImageOps
import tempfile
import os

# --- CONFIGURAZIONE PAGINA (Layout Wide per "Photoshop feel") ---
st.set_page_config(page_title="Pro Watermarker", layout="wide")

# --- CSS CUSTOM PER MIGLIORARE L'INTERFACCIA ---
st.markdown("""
<style>
    .stApp {background-color: #0e1117;} /* Sfondo scuro Pro */
    .stButton>button {width: 100%; border-radius: 5px; font-weight: bold;} 
    /* Rimuove padding eccessivo in alto */
    .block-container {padding-top: 2rem;}
</style>
""", unsafe_allow_html=True)

# --- GESTIONE STATO (MEMORIA) ---
if 'last_upload' not in st.session_state:
    st.session_state.last_upload = None
if 'target_w' not in st.session_state:
    st.session_state.target_w = 1080
if 'target_h' not in st.session_state:
    st.session_state.target_h = 1080

# --- SIDEBAR (PANNELLO CONTROLLI) ---
with st.sidebar:
    st.title("🎛️ Pannello Controlli")
    
    st.info("1. CARICA ASSETS")
    logo_file = st.file_uploader("Carica Logo (PNG)", type=['png', 'jpg'])
    
    # Anteprima piccolina del logo nel pannello
    logo_img = None
    if logo_file:
        logo_img = Image.open(logo_file)
        st.image(logo_img, width=100, caption="Logo Attivo")
        
        st.divider()
        st.info("2. POSIZIONE E STILE")
        
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            opacity = st.slider("Opacità", 0.1, 1.0, 0.9)
        with col_s2:
            scale = st.slider("Grandezza %", 5, 100, 20)
            
        position = st.selectbox("Posizione", 
            ["Basso Destra", "Basso Sinistra", "Alto Destra", "Alto Sinistra", "Centro"])
        
        margin_val = st.slider("Margine dai bordi (px)", 0, 200, 50)

# --- AREA PRINCIPALE ---
st.write("### 🖼️ Area di Lavoro")

tab_foto, tab_video = st.tabs(["FOTO EDITOR", "VIDEO LAB"])

# === LOGICA FOTO ===
with tab_foto:
    uploaded_photo = st.file_uploader("Trascina qui la tua foto", type=['jpg', 'jpeg', 'png', 'webp'])
    
    if uploaded_photo:
        image = Image.open(uploaded_photo)
        
        # --- AUTO-RILEVAMENTO DIMENSIONI ORIGINALI ---
        # Se è un nuovo file, aggiorniamo le dimensioni nello stato
        if uploaded_photo != st.session_state.last_upload:
            st.session_state.last_upload = uploaded_photo
            st.session_state.target_w = image.width
            st.session_state.target_h = image.height
            st.rerun() # Ricarica per aggiornare i campi

        # Controlli Dimensioni (messi qui per essere vicini all'immagine)
        st.markdown("#### 📏 Dimensioni Output")
        col_res1, col_res2, col_res3 = st.columns([1,1,2])
        with col_res1:
            new_w = st.number_input("Larghezza (px)", value=st.session_state.target_w, step=1)
        with col_res2:
            new_h = st.number_input("Altezza (px)", value=st.session_state.target_h, step=1)
        with col_res3:
            st.write(" ")
            st.caption(f"Originale: {image.width}x{image.height}")

        # --- ELABORAZIONE ---
        if logo_img:
            # 1. Ridimensiona Base
            base = ImageOps.pad(image, (new_w, new_h), color='white', centering=(0.5, 0.5))
            
            # 2. Prepara Logo
            wm = logo_img.copy()
            
            # Calcolo grandezza logo basato sulla larghezza della foto FINALE
            target_logo_w = int(new_w * (scale / 100))
            wm_ratio = wm.width / wm.height
            target_logo_h = int(target_logo_w / wm_ratio)
            
            if target_logo_w > 0 and target_logo_h > 0:
                wm = wm.resize((target_logo_w, target_logo_h), Image.Resampling.LANCZOS)
                
                # Opacità
                if wm.mode != 'RGBA': wm = wm.convert('RGBA')
                alpha = wm.split()[3]
                alpha = alpha.point(lambda p: p * opacity)
                wm.putalpha(alpha)
                
                # Posizione (con margine custom)
                if position == "Basso Destra":
                    pos = (new_w - target_logo_w - margin_val, new_h - target_logo_h - margin_val)
                elif position == "Basso Sinistra":
                    pos = (margin_val, new_h - target_logo_h - margin_val)
                elif position == "Alto Destra":
                    pos = (new_w - target_logo_w - margin_val, margin_val)
                elif position == "Alto Sinistra":
                    pos = (margin_val, margin_val)
                else:
                    pos = ((new_w - target_logo_w)//2, (new_h - target_logo_h)//2)
                
                # Unione
                canvas = Image.new('RGBA', base.size, (0,0,0,0))
                canvas.paste(wm, pos)
                final_image = Image.alpha_composite(base.convert('RGBA'), canvas).convert('RGB')
            else:
                final_image = base.convert('RGB')
                
            # Mostra risultato GRANDE
            st.image(final_image, caption=f"Anteprima {new_w}x{new_h}", use_column_width=True)
            
            # Download
            import io
            buf = io.BytesIO()
            final_image.save(buf, format="JPEG", quality=100)
            st.download_button("💾 SALVA FOTO", data=buf.getvalue(), file_name="foto_pro.jpg", mime="image/jpeg", type="primary")
        else:
            st.image(image, caption="Immagine Originale (Carica un logo per modificare)", use_column_width=True)

# === LOGICA VIDEO ===
with tab_video:
    st.write("⚠️ **Nota:** Il limite upload è aumentato, ma file > 500MB potrebbero essere lenti.")
    uploaded_video = st.file_uploader("Carica Video", type=['mp4', 'mov'])
    
    if uploaded_video and logo_img:
        if st.button("RENDERIZZA VIDEO (Start)"):
            with st.spinner("Rendering in corso... (non chiudere la pagina)"):
                try:
                    from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip
                    
                    tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
                    tfile.write(uploaded_video.read())
                    clip = VideoFileClip(tfile.name)
                    
                    # Logica Logo
                    vid_w, vid_h = clip.size
                    logo_w = int(vid_w * (scale / 100))
                    ratio = logo_img.width / logo_img.height
                    logo_h = int(logo_w / ratio)
                    
                    wm_res = logo_img.resize((logo_w, logo_h), Image.Resampling.LANCZOS)
                    wm_res.putalpha(wm_res.split()[3].point(lambda p: p * opacity))
                    wm_path = tempfile.mktemp(suffix=".png")
                    wm_res.save(wm_path)
                    
                    # Mapping posizione semplificato per MoviePy
                    pos_map = {
                        "Basso Destra": ("right", "bottom"), "Basso Sinistra": ("left", "bottom"),
                        "Alto Destra": ("right", "top"), "Alto Sinistra": ("left", "top"),
                        "Centro": ("center", "center")
                    }
                    
                    watermark = (ImageClip(wm_path)
                                 .set_duration(clip.duration)
                                 .set_pos(pos_map[position])
                                 .set_opacity(opacity)) # MoviePy opacity
                                 
                    final = CompositeVideoClip([clip, watermark])
                    out_path = tempfile.mktemp(suffix=".mp4")
                    
                    # Preset 'ultrafast' per evitare crash su server piccoli
                    final.write_videofile(out_path, codec="libx264", preset="ultrafast", audio_codec="aac", temp_audiofile='temp-audio.m4a', remove_temp=True, verbose=False, logger=None)
                    
                    st.video(out_path)
                    with open(out_path, "rb") as f:
                        st.download_button("💾 SCARICA VIDEO", f, "video_pro.mp4", "video/mp4")
                        
                except Exception as e:
                    st.error(f"Errore: {e}")
