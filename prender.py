
import requests


API = "http://127.0.0.1:8000"
TOKEN_BOT = "MTU1Njg2MDMwNjQ1NjU3NjEzMA.GYpLB9.HLcwxzXZcu9nvgPCeogrZBZ-FOnsoYfhy2T7og"

respuesta = requests.post(
    f"{API}/bot/iniciar",
    json={"bot_id": TOKEN_BOT},
    timeout=70
)

print("Estado:", respuesta.status_code)
print(respuesta.text)