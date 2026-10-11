
import subprocess
import sys
import os
import shutil

# En Render, configura esta variable en Environment.
# En Windows, puedes seguir utilizando cookies.txt localmente.
COOKIES_PATH = os.getenv(
    "YTDLP_COOKIES_FILE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt")
)


def get_youtube_audio_url(video_url):
    try:
        command = [
            sys.executable,
            "-m", "yt_dlp",
            "--no-playlist",
            "--no-warnings",
            "--js-runtimes", "deno",
            "-g",
            "-f", "bestaudio/best",
        ]

        # Solo usar cookies si el archivo existe.
        if os.path.isfile(COOKIES_PATH):
            command.extend(["--cookies", COOKIES_PATH])
        else:
            print("Archivo de cookies no encontrado; intentando sin cookies.")

        print("Extrayendo audio...")

        # Comprueba si Deno está disponible.
        if not shutil.which("deno"):
            print("Aviso: Deno no está disponible en el PATH.")

        result = subprocess.run(
            command + [video_url],
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )

        audio_url = result.stdout.strip().splitlines()

        if audio_url and audio_url[0].startswith("http"):
            print("URL obtenida correctamente.")
            return audio_url[0]

        print("No se encontró una URL de audio válida.")
        print(result.stderr[-2000:])
        return None

    except subprocess.TimeoutExpired:
        print("La extracción superó el límite de 120 segundos.")
        return None

    except subprocess.CalledProcessError as e:
        print("Error de yt-dlp:")
        print((e.stderr or str(e))[-4000:])
        return None

    except Exception as e:
        print(f"Error inesperado: {e}")
        return None
