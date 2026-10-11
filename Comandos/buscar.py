
import os
import sys
import shutil
import subprocess

# Carpeta donde se encuentra este archivo Python
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# En Render, puedes configurar esta variable de entorno.
# Si no existe, se utiliza cookies.txt junto al archivo Python.
COOKIES_PATH = os.getenv(
    "YTDLP_COOKIES_FILE",
    os.path.join(BASE_DIR, "cookies.txt")
)


def get_youtube_audio_url(video_url):
    try:
        if not video_url or not video_url.startswith(
            ("https://www.youtube.com/", "https://youtu.be/",
             "https://youtube.com/")
        ):
            print("Error: la URL de YouTube no es válida.")
            return None

        if not shutil.which("deno"):
            print(
                "Aviso: Deno no está disponible. "
                "Instálalo en el entorno de Render."
            )

        command = [
            sys.executable,
            "-m", "yt_dlp",
            "--no-playlist",
            "--js-runtimes", "deno",
            "--retries", "3",
            "--socket-timeout", "30",
            "-f", "bestaudio/best",
        ]

        # Utilizar cookies solo si el archivo existe.
        if os.path.isfile(COOKIES_PATH):
            command.extend(["--cookies", COOKIES_PATH])
            print("Archivo de cookies encontrado.")
        else:
            print(
                "No se encontró cookies.txt. "
                "Se intentará sin cookies."
            )

        command.extend(["-g", video_url])

        print("Extrayendo audio...")

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=BASE_DIR,
            check=True
        )

        urls = [
            line.strip()
            for line in result.stdout.splitlines()
            if line.strip().startswith("https://")
        ]

        if not urls:
            print("No se encontró una URL de audio.")
            if result.stderr:
                print(result.stderr[-3000:])
            return None

        print("URL obtenida correctamente.")
        return urls[0]

    except subprocess.TimeoutExpired:
        print("Error: tiempo de extracción agotado.")
        return None

    except subprocess.CalledProcessError as e:
        print("Error de yt-dlp:")
        print((e.stderr or str(e))[-4000:])
        return None

    except Exception as e:
        print(f"Error inesperado: {e}")
        return None
