import subprocess
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIES_PATH = os.path.join(BASE_DIR, "cookies.txt")


def get_youtube_audio_url(video_url):
    formatos = [
        "bestaudio/best",
        "best"
    ]

    for formato in formatos:
        try:
            command = [
                sys.executable,
                "-m",
                "yt_dlp",
                "--no-warnings",
                "--no-playlist",
                "--format", formato,
                "--get-url"
            ]

            # Utilizar las cookies si existen
            if os.path.isfile(COOKIES_PATH):
                command.extend(["--cookies", COOKIES_PATH])
                print("Usando cookies de YouTube.")
            else:
                print("ADVERTENCIA: No se encontró cookies.txt en:", COOKIES_PATH)

            command.append(video_url)

            print(f"Extrayendo audio con formato: {formato}")

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=90,
                cwd=BASE_DIR
            )

            if result.returncode == 0:
                urls = [
                    line.strip()
                    for line in result.stdout.splitlines()
                    if line.strip().startswith("https://")
                ]

                if urls:
                    print("URL de audio obtenida correctamente.")
                    return urls[0]

            print("Error de yt-dlp:")
            print(result.stderr)

        except subprocess.TimeoutExpired:
            print("Tiempo de espera agotado.")

        except Exception as e:
            print(f"Error inesperado: {e}")

    print("No se pudo obtener una URL de audio.")
    return None
