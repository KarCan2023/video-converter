# Media Converter (Legal) — Streamlit

App de Streamlit para convertir videos y audios **que tú posees o que estén bajo licencia válida**.
- **No descarga de YouTube** ni otras plataformas de streaming.
- Sube un archivo o pega una **URL directa** a un archivo (no páginas con reproductor).
- Salida a **MP4 (H.264 + AAC)** con resolución seleccionable y control de calidad (CRF).
- Extracción a **MP3** con bitrates desde 96 a 320 kbps.
- Opción de **normalizar audio** (loudness).

## Ejecutar localmente

```bash
python -m venv .venv && . .venv/bin/activate  # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

> La app usa `imageio-ffmpeg` para obtener un binario de FFmpeg portable. No necesitas instalar FFmpeg manualmente.

## Notas legales
Usa este proyecto solo con contenido propio, de dominio público o con licencia que permita la descarga y transformación. Para tus videos en YouTube, utiliza **YouTube Studio** (botón *Download*) o **Google Takeout**.