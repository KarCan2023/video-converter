import os
import re
import tempfile
import subprocess
from urllib.parse import urlparse
import requests
import streamlit as st
import imageio_ffmpeg
import pathlib
import yt_dlp

# -----------------------------
# Helpers
# -----------------------------

VALID_VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
VALID_AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
VALID_EXTS = VALID_VIDEO_EXTS | VALID_AUDIO_EXTS

def sanitize_filename(name: str) -> str:
    name = re.sub(r"[^\w\-\. ]+", "_", name, flags=re.UNICODE)
    name = re.sub(r"\s+", "_", name).strip("_")
    return name or "output"

def get_ffmpeg_path() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()

def save_upload_to_temp(uploaded_file) -> str:
    suffix = pathlib.Path(uploaded_file.name).suffix.lower()
    if suffix not in VALID_EXTS:
        suffix = ".bin"
    fd, temp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    with open(temp_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return temp_path

def download_direct_url_to_temp(url: str) -> str:
    parsed = urlparse(url)
    if not (parsed.scheme in ("http", "https") and parsed.netloc):
        raise ValueError("URL inválida.")
    
    ext = pathlib.Path(parsed.path).suffix.lower()
    if ext and ext not in VALID_EXTS:
        ext = ".bin"
    elif not ext:
        ext = ".bin"

    resp = requests.get(url, stream=True, timeout=30)
    resp.raise_for_status()
    fd, temp_path = tempfile.mkstemp(suffix=ext)
    os.close(fd)
    with open(temp_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1 << 20):
            if chunk:
                f.write(chunk)
    return temp_path

def download_youtube_to_temp(url: str) -> str:
    """
    Descarga video/audio de YouTube usando yt-dlp con FFmpeg empaquetado
    """
    # Obtener FFmpeg de imageio_ffmpeg
    ffmpeg_path = get_ffmpeg_path()
    
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': os.path.join(tempfile.gettempdir(), '%(id)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'ffmpeg_location': ffmpeg_path,  # ¡CRUCIAL! Usar FFmpeg empaquetado
        'merge_output_format': 'mp4',
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=True)
            downloaded_file = ydl.prepare_filename(info)
            
            # Si el archivo tiene extensión diferente, buscar el descargado
            if not os.path.exists(downloaded_file):
                temp_dir = tempfile.gettempdir()
                video_id = info.get('id', '')
                for file in os.listdir(temp_dir):
                    if file.startswith(video_id):
                        downloaded_file = os.path.join(temp_dir, file)
                        break
            
            # Crear copia temporal con extensión correcta
            fd, temp_path = tempfile.mkstemp(suffix=".mp4")
            os.close(fd)
            
            with open(downloaded_file, 'rb') as src, open(temp_path, 'wb') as dst:
                dst.write(src.read())
            
            # Limpiar archivo original descargado
            try:
                os.remove(downloaded_file)
            except:
                pass
                
            return temp_path
            
        except Exception as e:
            raise Exception(f"Error descargando de YouTube: {str(e)}")

def transcode_to_mp4(input_path: str, out_res: str, crf: int, audio_k: int, fast_preset: str, normalize_audio: bool):
    ffmpeg = get_ffmpeg_path()
    fd, out_path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    
    vf = []
    if out_res != "Original":
        h = {"360p": 360, "480p": 480, "720p": 720, "1080p": 1080}[out_res]
        vf.append(f"scale=-2:{h}")
    
    vf_arg = []
    if vf:
        vf_arg = ["-vf", ",".join(vf)]
    
    audio_filters = []
    if normalize_audio:
        audio_filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")
    
    af_arg = []
    if audio_filters:
        af_arg = ["-af", ",".join(audio_filters)]
    
    cmd = [
        ffmpeg, "-y", "-i", input_path,
        *vf_arg,
        "-c:v", "libx264",
        "-preset", fast_preset,
        "-crf", str(crf),
        "-c:a", "aac",
        "-b:a", f"{audio_k}k",
        *af_arg,
        "-movflags", "+faststart",
        out_path
    ]
    run_ffmpeg(cmd)
    return out_path

def extract_to_mp3(input_path: str, bitrate_k: int, normalize_audio: bool):
    ffmpeg = get_ffmpeg_path()
    fd, out_path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    
    audio_filters = []
    if normalize_audio:
        audio_filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")
    
    af_arg = []
    if audio_filters:
        af_arg = ["-af", ",".join(audio_filters)]
    
    cmd = [
        ffmpeg, "-y", "-i", input_path,
        *af_arg,
        "-vn",
        "-c:a", "libmp3lame",
        "-b:a", f"{bitrate_k}k",
        out_path
    ]
    run_ffmpeg(cmd)
    return out_path

def run_ffmpeg(cmd: list):
    with subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True
    ) as proc:
        log_lines = []
        for line in proc.stdout:
            log_lines.append(line.rstrip())
            if len(log_lines) % 25 == 0:
                st.write("⏳ FFmpeg:", log_lines[-1])
        ret = proc.wait()
        if ret != 0:
            raise RuntimeError("FFmpeg falló. Revisa el archivo de entrada y los parámetros.")

# -----------------------------
# UI
# -----------------------------

st.set_page_config(page_title="Media Converter", page_icon="🎬", layout="centered")
st.title("🎬 Conversor de video/audio")
st.markdown(
    """
**Importante:** Solo descarga contenido de YouTube cuando tengas los derechos o permiso para hacerlo.
"""
)

with st.expander("⚖️ Aviso legal (léelo)", expanded=False):
    st.write(
        "Este proyecto está pensado para uso legítimo: "
        "1. Tus propios videos subidos a YouTube\n"
        "2. Material con licencia Creative Commons\n"
        "3. Contenido de dominio público\n"
        "4. Videos donde el autor permite la descarga\n\n"
        "**No descargues contenido protegido por derechos de autor sin permiso.**"
    )

source = st.radio("Origen del archivo", 
                  ["Subir archivo", "URL directa", "YouTube"], 
                  horizontal=True)

input_temp_path = None
orig_name = "entrada"

try:
    if source == "Subir archivo":
        up = st.file_uploader("Sube tu video/audio", 
                              type=[e.strip(".") for e in sorted(VALID_EXTS)])
        if up:
            input_temp_path = save_upload_to_temp(up)
            orig_name = up.name
            
    elif source == "URL directa":
        url = st.text_input("Pega una URL directa a un archivo de video/audio")
        if url:
            if st.button("Descargar archivo"):
                with st.spinner("Descargando..."):
                    input_temp_path = download_direct_url_to_temp(url)
                    orig_name = os.path.basename(urlparse(url).path) or "archivo"
                    
    else:  # YouTube
        url = st.text_input("Pega la URL de YouTube")
        if url:
            if st.button("Descargar de YouTube"):
                with st.spinner("Descargando de YouTube..."):
                    try:
                        input_temp_path = download_youtube_to_temp(url)
                        
                        # Obtener título del video para nombre del archivo
                        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                            info = ydl.extract_info(url, download=False)
                            orig_name = info.get('title', 'video_youtube') + ".mp4"
                        st.success("¡Descarga completada!")
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
                        st.info("Asegúrate que la URL de YouTube sea válida y el video esté disponible.")

    if input_temp_path and os.path.exists(input_temp_path):
        st.success("Archivo listo ✔️")

        tab1, tab2 = st.tabs(["▶️ MP4 (video)", "🎵 MP3 (audio)"])
        
        with tab1:
            col1, col2 = st.columns(2)
            with col1:
                out_res = st.selectbox("Resolución", 
                                      ["Original", "360p", "480p", "720p", "1080p"])
                crf = st.slider("Calidad (CRF) – menor es mejor", 18, 30, 23)
            with col2:
                audio_k = st.select_slider("Bitrate de audio (kbps)", 
                                          options=[96, 128, 160, 192, 224, 256, 320], 
                                          value=160)
                preset = st.selectbox("Preset (velocidad vs calidad)", 
                                     ["ultrafast","superfast","veryfast","faster",
                                      "fast","medium","slow","slower","veryslow"], 
                                     index=5)
            normalize_v = st.checkbox("Normalizar audio (loudness)", 
                                     value=False, 
                                     help="Aplica loudnorm para volúmenes consistentes.")
            
            if st.button("Convertir a MP4", type="primary", key="convert_mp4"):
                with st.spinner("Convirtiendo a MP4..."):
                    out_path = transcode_to_mp4(input_temp_path, out_res, crf, 
                                               audio_k, preset, normalize_v)
                    base_name = sanitize_filename(os.path.splitext(orig_name)[0])
                    out_name = f"{base_name}_{out_res if out_res!='Original' else 'orig'}_crf{crf}_{audio_k}k.mp4"
                    
                    with open(out_path, "rb") as f:
                        st.download_button("⬇️ Descargar MP4", data=f.read(), 
                                         file_name=out_name, mime="video/mp4")

        with tab2:
            bitrate = st.select_slider("Bitrate MP3 (kbps)", 
                                      options=[96, 128, 160, 192, 224, 256, 320], 
                                      value=192)
            normalize_a = st.checkbox("Normalizar audio (loudness)", value=False)
            
            if st.button("Convertir a MP3", type="primary", key="convert_mp3"):
                with st.spinner("Extrayendo a MP3..."):
                    out_path = extract_to_mp3(input_temp_path, bitrate, normalize_a)
                    base_name = sanitize_filename(os.path.splitext(orig_name)[0])
                    out_name = f"{base_name}_{bitrate}k.mp3"
                    
                    with open(out_path, "rb") as f:
                        st.download_button("⬇️ Descargar MP3", data=f.read(), 
                                         file_name=out_name, mime="audio/mpeg")

except Exception as e:
    st.error(f"Error: {e}")
    st.stop()
