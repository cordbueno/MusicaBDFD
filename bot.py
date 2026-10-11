
import asyncio
import logging
from collections import defaultdict, deque

import discord
from discord.ext import commands

from Comandos.youtube import youtube_search
from Comandos.buscar import get_youtube_audio_url

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True

        super().__init__(command_prefix="!", intents=intents)

        self._connect_task = None
        self.queues = defaultdict(deque)
        self.current = {}
        self.playback_status = {}
        self._queue_locks = {}

    def _lock(self, guild_id):
        if guild_id not in self._queue_locks:
            self._queue_locks[guild_id] = asyncio.Lock()
        return self._queue_locks[guild_id]

    async def iniciar(self, token):
        if self.is_ready():
            return {
                "mensaje": "El bot ya está iniciado",
                "bot_id": str(self.user.id)
            }

        await self.login(token)

        self._connect_task = asyncio.create_task(
            self.connect(reconnect=True)
        )

        try:
            await asyncio.wait_for(
                self.wait_until_ready(),
                timeout=60
            )
        except asyncio.TimeoutError:
            self._connect_task.cancel()
            await self.close()
            raise RuntimeError(
                "El bot no se conectó a Discord a tiempo"
            )

        return {
            "mensaje": "Bot iniciado correctamente",
            "bot_id": str(self.user.id),
            "nombre": str(self.user)
        }

    def _extraer_url(self, resultado):
        if isinstance(resultado, str):
            if resultado.startswith(("https://", "http://")):
                return resultado
            raise ValueError("La búsqueda no devolvió una URL válida")

        if isinstance(resultado, dict):
            for clave in ("webpage_url", "url", "video_url", "link"):
                valor = resultado.get(clave)
                if isinstance(valor, str) and valor.startswith("http"):
                    return valor

            for clave in ("videos", "results", "items"):
                lista = resultado.get(clave)
                if lista:
                    return self._extraer_url(lista[0])

        if isinstance(resultado, (list, tuple)) and resultado:
            return self._extraer_url(resultado[0])

        raise ValueError(
            "No se pudo extraer la URL del resultado de YouTube"
        )

    def _extraer_titulo(self, resultado, query):
        if isinstance(resultado, dict):
            return (
                resultado.get("title")
                or resultado.get("titulo")
                or query
            )

        if isinstance(resultado, (list, tuple)) and resultado:
            return self._extraer_titulo(resultado[0], query)

        return query

    async def agregar_a_cola(self, guild_id, channel_id, query):
        guild = self.get_guild(guild_id)

        if guild is None:
            raise ValueError("El bot no está en ese servidor")

        canal = guild.get_channel(channel_id)

        if not isinstance(
            canal,
            (discord.VoiceChannel, discord.StageChannel)
        ):
            raise ValueError("El canal de voz no es válido")

        resultado = await asyncio.to_thread(youtube_search, query)

        url = self._extraer_url(resultado)
        titulo = self._extraer_titulo(resultado, query)

        elemento = {
            "titulo": titulo,
            "url": url,
            "resultado": resultado,
            "query": query
        }

        async with self._lock(guild_id):
            voice = guild.voice_client

            if voice is None:
                voice = await canal.connect()
            elif voice.channel.id != channel_id:
                await voice.move_to(canal)

            self.queues[guild_id].append(elemento)
            posicion = len(self.queues[guild_id])

            self.playback_status[guild_id] = (
                "reproduciendo"
                if voice.is_playing() or voice.is_paused()
                else "pendiente"
            )

            if not voice.is_playing() and not voice.is_paused():
                await self._iniciar_siguiente(guild_id)

        return {
            "mensaje": "Se agregó la música a la cola",
            "cancion": titulo,
            "url": url,
            "posicion": posicion,
            "estado": self.playback_status.get(
                guild_id, "pendiente"
            )
        }

    async def reproducir_audio(self, guild_id, channel_id, query):
        return await self.agregar_a_cola(
            guild_id, channel_id, query
        )

    async def _iniciar_siguiente(self, guild_id):
        guild = self.get_guild(guild_id)

        if guild is None:
            return

        voice = guild.voice_client

        if voice is None or not voice.is_connected():
            self.playback_status[guild_id] = "desconectado"
            return

        if voice.is_playing() or voice.is_paused():
            return

        if not self.queues[guild_id]:
            self.current.pop(guild_id, None)
            self.playback_status[guild_id] = "cola_vacia"
            return

        elemento = self.queues[guild_id].popleft()

        try:
            url_audio = await asyncio.to_thread(
                get_youtube_audio_url,
                elemento["resultado"]
            )

            if not url_audio:
                raise RuntimeError("No se pudo obtener el audio")

            fuente = discord.FFmpegPCMAudio(
                url_audio,
                before_options=(
                    "-reconnect 1 "
                    "-reconnect_streamed 1 "
                    "-reconnect_delay_max 5"
                ),
                options="-vn"
            )

            loop = asyncio.get_running_loop()

            self.current[guild_id] = elemento
            self.playback_status[guild_id] = "reproduciendo"

            def al_terminar(error):
                if error:
                    logger.error(
                        "Error de reproducción: %s", error
                    )

                asyncio.run_coroutine_threadsafe(
                    self._terminar_y_continuar(guild_id, error),
                    loop
                )

            voice.play(fuente, after=al_terminar)

        except Exception as error:
            logger.exception("Error al iniciar la canción")
            self.playback_status[guild_id] = "error"
            self.current.pop(guild_id, None)

            self.playback_status[guild_id] = "saltando_error"
            await self._iniciar_siguiente(guild_id)

    async def _terminar_y_continuar(self, guild_id, error):
        async with self._lock(guild_id):
            self.current.pop(guild_id, None)

            if error:
                self.playback_status[guild_id] = "error"
            else:
                self.playback_status[guild_id] = "terminada"

            await self._iniciar_siguiente(guild_id)

    async def obtener_cola(self, guild_id):
        actual = self.current.get(guild_id)

        return {
            "mensaje": (
                "Inició la reproducción"
                if actual
                else "No hay música reproduciéndose"
            ),
            "estado": self.playback_status.get(
                guild_id, "cola_vacia"
            ),
            "reproduciendo": (
                {
                    "cancion": actual["titulo"],
                    "url": actual["url"]
                }
                if actual else None
            ),
            "cola": [
                {
                    "cancion": elemento["titulo"],
                    "url": elemento["url"]
                }
                for elemento in self.queues[guild_id]
            ],
            "cantidad": len(self.queues[guild_id])
        }

    async def siguiente(self, guild_id):
        guild = self.get_guild(guild_id)

        if guild is None or guild.voice_client is None:
            raise ValueError("El bot no está conectado a un canal de voz")

        async with self._lock(guild_id):
            voice = guild.voice_client

            if voice.is_playing() or voice.is_paused():
                voice.stop()
            else:
                self.current.pop(guild_id, None)
                await self._iniciar_siguiente(guild_id)

        return {"mensaje": "Se solicitó pasar a la siguiente canción"}

    async def detener_audio(self, guild_id):
        guild = self.get_guild(guild_id)

        if guild is None:
            raise ValueError("Servidor no encontrado")

        async with self._lock(guild_id):
            self.queues[guild_id].clear()
            self.current.pop(guild_id, None)
            self.playback_status[guild_id] = "detenida"

            if guild.voice_client:
                if (
                    guild.voice_client.is_playing()
                    or guild.voice_client.is_paused()
                ):
                    guild.voice_client.stop()

        return {
            "mensaje": "Reproducción detenida y cola vaciada",
            "estado": "detenida"
        }

    async def pausar_audio(self, guild_id):
        guild = self.get_guild(guild_id)

        if guild and guild.voice_client and guild.voice_client.is_playing():
            guild.voice_client.pause()
            self.playback_status[guild_id] = "pausada"
            return {"mensaje": "Música pausada", "estado": "pausada"}

        raise ValueError("No hay música reproduciéndose")

    async def reanudar_audio(self, guild_id):
        guild = self.get_guild(guild_id)

        if guild and guild.voice_client and guild.voice_client.is_paused():
            guild.voice_client.resume()
            self.playback_status[guild_id] = "reproduciendo"
            return {
                "mensaje": "Música reanudada",
                "estado": "reproduciendo"
            }

        raise ValueError("No hay música pausada")

    async def salir_canal(self, guild_id):
        guild = self.get_guild(guild_id)

        if guild is None:
            raise ValueError("Servidor no encontrado")

        async with self._lock(guild_id):
            self.queues[guild_id].clear()
            self.current.pop(guild_id, None)
            self.playback_status[guild_id] = "desconectado"

            if guild.voice_client:
                await guild.voice_client.disconnect()

        return {"mensaje": "Bot desconectado", "estado": "desconectado"}

    async def obtener_estado(self):
        return {
            "conectado": self.is_ready(),
            "bot_id": str(self.user.id) if self.user else None,
            "nombre": str(self.user) if self.user else None
        }


class MusicBotManager:
    def __init__(self):
        self.bots = {}
        self.lock = asyncio.Lock()

    async def iniciar(self, token):
        async with self.lock:
            bot = self.bots.get(token)

            if bot and bot.is_ready():
                return {
                    "mensaje": "El bot ya está iniciado",
                    "bot_id": str(bot.user.id)
                }

            if bot:
                await bot.close()

            bot = MusicBot()
            self.bots[token] = bot

        try:
            return await bot.iniciar(token)
        except Exception:
            async with self.lock:
                if self.bots.get(token) is bot:
                    self.bots.pop(token, None)
            raise

    def obtener_bot(self, token):
        bot = self.bots.get(token)

        if bot is None or not bot.is_ready():
            raise RuntimeError("El bot no está iniciado")

        return bot

    async def obtener_estado(self):
        estados = {}

        for bot in self.bots.values():
            if bot.is_ready():
                estados[str(bot.user.id)] = await bot.obtener_estado()

        return estados

    async def cerrar_todos(self):
        for bot in list(self.bots.values()):
            await bot.close()

        self.bots.clear()


music_bots = MusicBotManager()
