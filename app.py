import streamlit as st
from PIL import Image, ImageOps
import tempfile
import os

# Titolo e configurazione
st.set_page_config(page_title="App Logo Maker", layout="centered")
st.title("Applica Logo e Ridimensiona")

# --- BARRA LATERALE (UPLOAD LOGO) ---
st.sidebar.header("1. Carica il Logo")
logo_file = st.sidebar.file_uploader("Carica qui il tuo Logo (PNG)", type=['png', 'jpg'])

logo_img = None
if logo_file:
    logo_img = Image.open(logo_file)
    st.sidebar.image(logo_img, width=100, caption="Il tuo logo")
    # Opzioni Logo
    opacity = st.sidebar.slider("Trasparenza Logo", 0.0, 1.0, 0.9)
    logo_scale = st.sidebar.slider("Grandezza Logo (%)", 10, 50, 20) / 100
    position = st.sidebar.selectbox("Posizione", ["Basso Destra", "Basso Sinistra", "Alto Destra", "Alto Sinistra", "Centro"])

# --- TAB FOTO E VIDEO ---
tab_foto, tab_video = st.tabs(["FOTO", "VIDEO"])

with tab_foto:
    st.header("Carica Foto")
    uploaded_photo = st.file_uploader("Scegli la foto", type=['jpg', 'png', 'jpeg'])

    if uploaded_photo and logo_img:
        # 1. Carica immagine base
        base_img = Image.open(uploaded_photo).convert("RGBA")
        
        # 2. Ridimensionamento per Social
        formato = st.selectbox("Formato Social", ["Originale", "Post Instagram (Quadrato)", "Storia Instagram (Verticale)"])
        
        if formato == "Post Instagram (Quadrato)":
            base_img = ImageOps.pad(base_img, (1080, 1080), color='white', centering=(0.5, 0.5))
        elif formato == "Storia Instagram (Verticale)":
            base_img = ImageOps.pad(base_img, (1080, 1920), color='white', centering=(0.5, 0.5))
            
        # 3. Applica Logo
        # Calcola dimensioni logo
        w, h = base_img.size
        logo_w = int(w * logo_scale)
        aspect_ratio = logo_img.width / logo_img.height
        logo_h = int(logo_w / aspect_ratio)
        
        logo_resized = logo_img.resize((logo_w, logo_h))
        
        # Applica trasparenza
        if logo_resized.mode != 'RGBA':
            logo_resized = logo_resized.convert('RGBA')
        r, g, b, alpha = logo_resized.split()
        alpha = alpha.point(lambda p: p * opacity)
        logo_resized.putalpha(alpha)
        
        # Calcola posizione (coordinate x, y)
        padding = int(w * 0.05)
        if position == "Basso Destra":
            pos = (w - logo_w - padding, h - logo_h - padding)
        elif position == "Basso Sinistra":
            pos = (padding, h - logo_h - padding)
        elif position == "Alto Destra":
            pos = (w - logo_w - padding, padding)
        elif position == "Alto Sinistra":
            pos = (padding, padding)
        else:
            pos = ((w - logo_w)//2, (h - logo_h)//2)
            
        # Unisci
        final_img = Image.new("RGBA", base_img.size)
        final_img.paste(base_img, (0,0))
        final_img.paste(logo_resized, pos, mask=logo_resized)
        final_img = final_img.convert("RGB")
        
        st.image(final_img, caption="Risultato")
        
        # Tasto Download
        import io
        buf = io.BytesIO()
        final_img.save(buf, format="JPEG", quality=100)
        st.download_button("Scarica Foto", data=buf.getvalue(), file_name="foto_con_logo.jpg", mime="image/jpeg")

with tab_video:
    st.write("Per i video, usa la tab Foto per creare una copertina, oppure contattami per attivare la funzione video avanzata (richiede server più potenti).")
