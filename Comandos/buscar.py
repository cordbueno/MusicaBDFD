import os
from pathlib import Path
from typing import Any

import yt_dlp

BASE_DIR = Path(__file__).resolve().parent
COOKIES_PATH = BASE_DIR / "cookies.txt"


def get_youtube_audio_info(video_url: str) -> dict[str, Any] | None:
    """Obtiene una URL reciente de audio y los encabezados HTTP para FFmpeg."""
    options = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": False,
        "extractor_retries": 3,
        "socket_timeout": 30,
        "remote_components": ["ejs:github"],
    }

    # Usa cookies únicamente si el archivo existe en el contenedor.
    if COOKIES_PATH.is_file():
        options["cookiefile"] = str(COOKIES_PATH)

    try:
        print(f"Extrayendo información de audio: {video_url}")
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(video_url, download=False)

        if not info:
            print("yt-dlp no devolvió información del video.")
            return None

        audio_url = info.get("url")
        headers = info.get("http_headers") or {}

        if not audio_url:
            # Respaldo por si yt-dlp devuelve los formatos en vez de la URL principal.
            formats = info.get("formats") or []
            audio_formats = [
                item for item in formats
                if item.get("url") and item.get("acodec") != "none"
            ]
            if audio_formats:
                selected = audio_formats[-1]
                audio_url = selected.get("url")
                headers = selected.get("http_headers") or headers

        if not audio_url:
            print("No se encontró una URL directa de audio.")
            return None

        # FFmpeg suele necesitar un User-Agent y Referer coherentes con la extracción.
        headers = dict(headers)
        headers.setdefault(
            "User-Agent",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        )
        headers.setdefault("Referer", "https://www.youtube.com/")

        print("URL de audio y encabezados obtenidos correctamente.")
        return {"url": audio_url, "headers": headers}

    except Exception as exc:
        print(f"Error de yt-dlp: {exc}")
        return None


def get_youtube_audio_url(video_url: str) -> str | None:
    """Compatibilidad con código que solo necesita la URL de audio."""
    info = get_youtube_audio_info(video_url)
    return info["url"] if info else None
