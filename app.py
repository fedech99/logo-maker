import streamlit as st
from PIL import Image, ImageOps
import os
import tempfile

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Batch Editor", layout="wide")

# --- FUNZIONI UTILI ---
def load_local_logos():
    """Cerca i loghi nella cartella 'logos' su GitHub/Server"""
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

def apply_watermark(base, watermark, position, scale, opacity, margin_px):
    # Logica ottimizzata per batch
    base_w, base_h = base.size
    
    # Calcolo dimensioni logo
    target_w = int(base_w * (scale / 100))
    aspect = watermark.width / watermark.height
    target_h = int(target_w / aspect)
    
    if target_w < 1 or target_h < 1: return base

    # Resize e Opacità
    wm = watermark.resize((target_w, target_h), Image.Resampling.LANCZOS)
    if wm.mode != 'RGBA': wm = wm.convert('RGBA')
    
    # Applicazione Opacità veloce
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

# --- SIDEBAR: LIBRERIA LOGHI ---
with st.sidebar:
    st.header("📂 Libreria Loghi")
    
    # 1. Carica loghi dalla cartella 'logos'
    library_logos = load_local_logos()
    
    # 2. Permetti upload manuale temporaneo
    uploaded_logo = st.file_uploader("Aggiungi logo temporaneo", type=['png', 'jpg'])
    if uploaded_logo:
        library_logos[uploaded_logo.name] = Image.open(uploaded_logo)
    
    # SELETTORE LOGO
    if not library_logos:
        st.warning("Nessun logo trovato. Caricane uno o crea la cartella 'logos' su GitHub.")
        active_logo = None
    else:
        logo_names = list(library_logos.keys())
        selected_name = st.selectbox("Seleziona Logo attivo:", logo_names)
        active_logo = library_logos[selected_name]
        
        # Mostra anteprima piccola del logo selezionato
        st.image(active_logo, width=120, caption="Logo in uso")
        
        st.divider()
        st.subheader("🛠 Impostazioni")
        scale = st.slider("Grandezza %", 5, 80, 20)
        opacity = st.slider("Opacità", 0.1, 1.0, 0.9)
        margin = st.slider("Margine (px)", 0, 300, 50)
        pos = st.selectbox("Posizione", ["Basso Destra", "Basso Sinistra", "Alto Destra", "Alto Sinistra", "Centro"])

# --- INTERFACCIA PRINCIPALE ---
st.title("Batch Watermarker")

if not active_logo:
    st.info("👈 Seleziona o carica un logo dalla barra laterale per iniziare.")
else:
    # UPLOAD MULTIPLO
    uploaded_files = st.file_uploader("Trascina qui le tue foto (ne puoi mettere tante)", 
                                      accept_multiple_files=True, 
                                      type=['jpg', 'png', 'webp'])

    if uploaded_files:
        st.write(f"📸 **{len(uploaded_files)} foto caricate**")
        
        # Opzioni Output
        col_opt1, col_opt2 = st.columns(2)
        with col_opt1:
            resize_mode = st.checkbox("Ridimensiona tutte?", value=False)
        with col_opt2:
            if resize_mode:
                col_w, col_h = st.columns(2)
                w_req = col_w.number_input("Larghezza Max", value=1080)
                h_req = col_h.number_input("Altezza Max", value=1350)

        st.divider()
        
        # --- GRIGLIA ANTEPRIME (GALLERY) ---
        # Creiamo colonne dinamiche (3 per riga)
        cols = st.columns(3)
        
        # ZIP FILE (Se servisse scaricare tutto insieme - opzionale futuro)
        
        for i, file in enumerate(uploaded_files):
            image = Image.open(file)
            
            # Ridimensionamento opzionale
            if resize_mode:
                image = ImageOps.pad(image, (w_req, h_req), color='white', centering=(0.5, 0.5))
            
            # Applica Logo
            processed = apply_watermark(image, active_logo, pos, scale, opacity, margin)
            
            # Mostra nella colonna giusta
            col_idx = i % 3
            with cols[col_idx]:
                st.image(processed, use_column_width=True)
                
                # Tasto download singolo sotto ogni foto
                import io
                buf = io.BytesIO()
                processed.save(buf, format="JPEG", quality=95)
                st.download_button(f"⬇️ Scarica {i+1}", data=buf.getvalue(), file_name=f"edit_{file.name}", mime="image/jpeg", key=f"dl_{i}")
