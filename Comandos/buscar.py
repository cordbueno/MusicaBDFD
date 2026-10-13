
import yt_dlp

def get_youtube_audio_url(video_url):
    opciones = {
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }

    try:
        with yt_dlp.YoutubeDL(opciones) as ydl:
            info = ydl.extract_info(video_url, download=False)
            return info["url"]

    except Exception as e:
        print(f"Error: {e}")
        return None


