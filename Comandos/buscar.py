import subprocess
import sys
import os

COOKIES_PATH = "cookies.txt"


def get_youtube_audio_url(video_url):
    try:
        command = [
            sys.executable,
            "-m",
            "yt_dlp",
            "-g",
            "-f",
            "bestaudio/best",
            "--cookies",
            COOKIES_PATH,
            video_url
        ]

        print("Extrayendo audio...")

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )

        audio_url = result.stdout.strip()

        if audio_url:
            print("URL obtenida correctamente.")
            return audio_url

        print("No se encontró la URL del audio.")
        return None

    except subprocess.CalledProcessError as e:
        print("Error de yt-dlp:")
        print(e.stderr)
        return None

    except Exception as e:
        print(f"Error inesperado: {e}")
        return None

