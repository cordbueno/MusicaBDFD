import requests


API = "http://127.0.0.1:8000"

TOKEN_BOT = ""
GUILD_ID = 1556757557341593751
CHANNEL_ID = 1556757557790376222

cancion = "Shawn Mendes, Camila Cabello - Señorita"

respuesta = requests.post(
    f"{API}/musica/reproducir",
    json={
        "bot_id": TOKEN_BOT,
        "guild_id": GUILD_ID,
        "channel_id": CHANNEL_ID,
        "query": cancion
    },
    timeout=120
)

print("Código:", respuesta.status_code)
print(respuesta.text)