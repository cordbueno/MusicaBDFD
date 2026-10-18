import os
import yt_dlp


# Ruta de cookies.txt, si existe.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIES_PATH = os.path.abspath(
    os.path.join(BASE_DIR, "..", "cookies.txt")
)


def get_youtube_audio_url(url):
    """
    Obtiene una URL de audio de YouTube y sus cabeceras HTTP.

    Acepta:
    - Una URL de YouTube.
    - Un diccionario con información del video.
    - Un resultado de búsqueda que contenga la URL o el ID.
    """

    opciones = {
    "format": "bestaudio/best",
    "quiet": True,
    }

    with yt_dlp.YoutubeDL(opciones) as ydl:
        info = ydl.extract_info(url, download=False)
        return info["url"]
