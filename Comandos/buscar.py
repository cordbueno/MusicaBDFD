

import os
import yt_dlp

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIES_PATH = os.path.join(BASE_DIR, "cookies.txt")


def get_youtube_audio_url(video_url):
    opciones = {
        "format": "bestaudio/best",
        "cookiefile": COOKIES_PATH,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL(opciones) as ydl:
            info = ydl.extract_info(video_url, download=False)
            return info.get("url")

    except Exception as e:
        print(f"Error al obtener la URL: {e}")
        return None
