import subprocess
import sys
import os

# Ruta de la carpeta donde está este archivo
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Archivo de cookies
COOKIES_PATH = os.path.join(BASE_DIR, "cookies.txt")


def get_youtube_audio_url(video_url):
    try:
        command = [
            sys.executable,
            "-m",
            "yt_dlp",

            "--no-warnings",
            "--no-playlist",

            "-f",
            "bestaudio/best",

            "--get-url",

            "--extractor-args",
            "youtube:player_client=default",

            video_url
        ]

        # Utilizar cookies solo si el archivo existe
        if os.path.isfile(COOKIES_PATH):
            command[3:3] = [
                "--cookies",
                COOKIES_PATH
            ]

        print("Extrayendo audio...")

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=BASE_DIR,
            timeout=90
        )

        if result.returncode != 0:
            print("Error de yt-dlp:")
            print(result.stderr)
            return None

        # Obtener la URL generada
        urls = [
            line.strip()
            for line in result.stdout.splitlines()
            if line.strip().startswith("https://")
        ]

        if not urls:
            print("No se encontró ninguna URL de audio.")
            print(result.stdout)
            return None

        print("URL obtenida correctamente.")
        return urls[0]

    except subprocess.TimeoutExpired:
        print("Tiempo de espera agotado al obtener el audio.")
        return None

    except Exception as e:
        print(f"Error inesperado: {e}")
        return None
