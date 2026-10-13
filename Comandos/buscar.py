import os
import yt_dlp


# Ruta de cookies.txt, si existe.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIES_PATH = os.path.abspath(
    os.path.join(BASE_DIR, "..", "cookies.txt")
)


def get_youtube_audio_url(resultado):
    """
    Obtiene una URL de audio de YouTube y sus cabeceras HTTP.

    Acepta:
    - Una URL de YouTube.
    - Un diccionario con información del video.
    - Un resultado de búsqueda que contenga la URL o el ID.
    """

    video_url = None

    # Si ya recibimos una URL.
    if isinstance(resultado, str):
        video_url = resultado

    # Si recibimos un diccionario.
    elif isinstance(resultado, dict):

        video_url = (
            resultado.get("webpage_url")
            or resultado.get("video_url")
            or resultado.get("link")
        )

        # Si solamente tenemos el ID.
        if not video_url and resultado.get("id"):
            video_url = (
                "https://www.youtube.com/watch?v="
                + str(resultado["id"])
            )

        # Algunos buscadores utilizan url para guardar
        # la dirección del video.
        if not video_url and resultado.get("url"):
            posible_url = resultado["url"]

            if isinstance(posible_url, str):
                if posible_url.startswith("http"):
                    video_url = posible_url
                elif resultado.get("id"):
                    video_url = (
                        "https://www.youtube.com/watch?v="
                        + str(resultado["id"])
                    )

    # Si recibimos una lista de resultados.
    elif isinstance(resultado, (list, tuple)) and resultado:
        return get_youtube_audio_url(resultado[0])

    if not video_url:
        print("Error: no se encontró la URL del video.")
        return None

    # Configuración de yt-dlp.
    opciones = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }

    # Utiliza las cookies solo si el archivo existe.
    if os.path.isfile(COOKIES_PATH):
        opciones["cookiefile"] = COOKIES_PATH

    try:
        with yt_dlp.YoutubeDL(opciones) as ydl:
            info = ydl.extract_info(
                video_url,
                download=False
            )

            if not info:
                print("Error: YouTube no devolvió información.")
                return None

            url_audio = info.get("url")

            if not url_audio:
                print("Error: no se obtuvo la URL de audio.")
                return None

            # Guardamos las cabeceras que utiliza yt-dlp.
            headers = info.get("http_headers", {})

            return {
                "url": url_audio,
                "headers": headers,
                "titulo": info.get("title", "Audio de YouTube"),
                "duracion": info.get("duration"),
                "video_url": info.get("webpage_url", video_url),
            }

    except Exception as error:
        print(
            f"Error obteniendo el audio de YouTube: {error}"
        )
        return None
