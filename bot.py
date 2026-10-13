
import asyncio
import logging
from collections import defaultdict, deque

import discord
from discord.ext import commands

from Comandos.youtube import youtube_search
from Comandos.buscar import get_youtube_audio_url


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

logger = logging.getLogger("music_bot")


class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True

        super().__init__(
            command_prefix="!",
            intents=intents
        )

        # Tarea que mantiene la conexión con Discord.
        self._connect_task = None

        # Cola independiente para cada servidor.
        self.queues = defaultdict(deque)

        # Canción actualmente en reproducción.
        self.current = {}

        # Estado de reproducción por servidor.
        self.playback_status = {}

        # Bloqueos para evitar operaciones simultáneas.
        self._queue_locks = {}

    def _lock(self, guild_id):
        if guild_id not in self._queue_locks:
            self._queue_locks[guild_id] = asyncio.Lock()

        return self._queue_locks[guild_id]

    # --------------------------------------------------
    # INICIAR BOT
    # --------------------------------------------------

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
                "El bot no pudo conectarse a Discord a tiempo"
            )

        return {
            "mensaje": "Bot iniciado correctamente",
            "bot_id": str(self.user.id),
            "nombre": str(self.user)
        }

    # --------------------------------------------------
    # EXTRAER INFORMACIÓN DE YOUTUBE
    # --------------------------------------------------

    def _extraer_url(self, resultado):
        if isinstance(resultado, str):
            if resultado.startswith(("https://", "http://")):
                return resultado

            raise ValueError(
                "La búsqueda no devolvió una URL válida"
            )

        if isinstance(resultado, dict):
            for clave in (
                "webpage_url",
                "url",
                "video_url",
                "link"
            ):
                valor = resultado.get(clave)

                if (
                    isinstance(valor, str)
                    and valor.startswith("http")
                ):
                    return valor

            for clave in ("videos", "results", "items"):
                lista = resultado.get(clave)

                if lista:
                    return self._extraer_url(lista[0])

        if isinstance(resultado, (list, tuple)) and resultado:
            return self._extraer_url(resultado[0])

        raise ValueError(
            "No se pudo obtener la URL del video de YouTube"
        )

    def _extraer_titulo(self, resultado, query):
        if isinstance(resultado, dict):
            return (
                resultado.get("title")
                or resultado.get("titulo")
                or query
            )

        if isinstance(resultado, (list, tuple)) and resultado:
            return self._extraer_titulo(
                resultado[0],
                query
            )

        return query

    # --------------------------------------------------
    # AGREGAR CANCIÓN A LA COLA
    # --------------------------------------------------

    async def agregar_a_cola(
        self,
        guild_id,
        channel_id,
        query
    ):
        guild = self.get_guild(guild_id)

        if guild is None:
            raise ValueError(
                "El bot no está en el servidor indicado"
            )

        canal = guild.get_channel(channel_id)

        if not isinstance(
            canal,
            (discord.VoiceChannel, discord.StageChannel)
        ):
            raise ValueError(
                "El canal de voz no es válido"
            )

        # Buscar el video.
        resultado = await asyncio.to_thread(
            youtube_search,
            query
        )

        url = self._extraer_url(resultado)
        titulo = self._extraer_titulo(
            resultado,
            query
        )

        elemento = {
            "titulo": titulo,
            "url": url,
            "resultado": resultado,
            "query": query,
            "_intentos": 0
        }

        async with self._lock(guild_id):
            voice = guild.voice_client

            if voice is None:
                voice = await canal.connect()

            elif voice.channel.id != channel_id:
                await voice.move_to(canal)

            self.queues[guild_id].append(elemento)

            posicion = len(self.queues[guild_id])

            if voice.is_playing() or voice.is_paused():
                estado = "pendiente"
            else:
                estado = "pendiente"

            self.playback_status[guild_id] = estado

            if not voice.is_playing() and not voice.is_paused():
                await self._iniciar_siguiente(guild_id)

        return {
            "mensaje": "Se agregó la música a la cola",
            "cancion": titulo,
            "url": url,
            "posicion": posicion,
            "estado": self.playback_status.get(
                guild_id,
                "pendiente"
            )
        }

    async def reproducir_audio(
        self,
        guild_id,
        channel_id,
        query
    ):
        return await self.agregar_a_cola(
            guild_id,
            channel_id,
            query
        )

    # --------------------------------------------------
    # REPRODUCIR SIGUIENTE CANCIÓN
    # --------------------------------------------------

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

        while self.queues[guild_id]:
            elemento = self.queues[guild_id].popleft()

            try:
                # Actualizar el resultado de YouTube para intentar
                # obtener una URL de audio reciente.
                resultado = await asyncio.to_thread(
                    youtube_search,
                    elemento["query"]
                )

                url_audio = await asyncio.to_thread(
                    get_youtube_audio_url,
                    resultado
                )

                if not url_audio:
                    raise RuntimeError(
                        "No se obtuvo una URL de audio"
                    )

                # Configuración de FFmpeg para reconexiones.
                fuente = discord.FFmpegPCMAudio(
                    url_audio,
                    before_options=(
                        "-nostdin "
                        "-reconnect 1 "
                        "-reconnect_streamed 1 "
                        "-reconnect_at_eof 1 "
                        "-reconnect_delay_max 10 "
                        "-rw_timeout 15000000"
                    ),
                    options="-vn -loglevel warning"
                )

                loop = asyncio.get_running_loop()

                self.current[guild_id] = elemento
                self.playback_status[guild_id] = "reproduciendo"

                def al_terminar(error):
                    if error:
                        logger.error(
                            "Error durante '%s': %s",
                            elemento["titulo"],
                            error
                        )

                    asyncio.run_coroutine_threadsafe(
                        self._terminar_y_continuar(
                            guild_id,
                            elemento,
                            error
                        ),
                        loop
                    )

                voice.play(
                    fuente,
                    after=al_terminar
                )

                logger.info(
                    "Inició la reproducción: %s",
                    elemento["titulo"]
                )

                return

            except Exception:
                logger.exception(
                    "No se pudo iniciar '%s'",
                    elemento["titulo"]
                )

                elemento["_intentos"] += 1

                # Tres intentos en total.
                if elemento["_intentos"] < 3:
                    self.queues[guild_id].appendleft(elemento)
                    continue

                logger.error(
                    "Canción omitida después de tres intentos: %s",
                    elemento["titulo"]
                )

        self.current.pop(guild_id, None)
        self.playback_status[guild_id] = "cola_vacia"

    # --------------------------------------------------
    # CUANDO TERMINA O FALLA EL AUDIO
    # --------------------------------------------------

    async def _terminar_y_continuar(
        self,
        guild_id,
        elemento,
        error
    ):
        async with self._lock(guild_id):
            actual = self.current.get(guild_id)

            # Ignorar callbacks antiguos.
            if actual is not elemento:
                return

            self.current.pop(guild_id, None)

            if error:
                elemento["_intentos"] += 1

                if elemento["_intentos"] < 3:
                    logger.warning(
                        "Reintentando '%s'; intento %s de 3",
                        elemento["titulo"],
                        elemento["_intentos"] + 1
                    )

                    self.queues[guild_id].appendleft(elemento)
                else:
                    logger.error(
                        "Se omitió la canción: %s",
                        elemento["titulo"]
                    )

            else:
                logger.info(
                    "Terminó correctamente: %s",
                    elemento["titulo"]
                )

            await self._iniciar_siguiente(guild_id)

    # --------------------------------------------------
    # CONSULTAR COLA Y ESTADO
    # --------------------------------------------------

    async def obtener_cola(self, guild_id):
        actual = self.current.get(guild_id)

        guild = self.get_guild(guild_id)
        voice = guild.voice_client if guild else None

        if voice and voice.is_paused():
            estado = "pausada"
        elif voice and voice.is_playing():
            estado = "reproduciendo"
        elif actual:
            estado = self.playback_status.get(
                guild_id,
                "reproduciendo"
            )
        else:
            estado = self.playback_status.get(
                guild_id,
                "cola_vacia"
            )

        return {
            "mensaje": (
                "Inició la reproducción"
                if actual and estado == "reproduciendo"
                else "Estado de reproducción consultado"
            ),
            "estado": estado,
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

    # --------------------------------------------------
    # SIGUIENTE CANCIÓN
    # --------------------------------------------------

    async def siguiente(self, guild_id):
        guild = self.get_guild(guild_id)

        if guild is None or guild.voice_client is None:
            raise ValueError(
                "El bot no está conectado a un canal de voz"
            )

        async with self._lock(guild_id):
            voice = guild.voice_client

            if not self.queues[guild_id]:
                raise ValueError(
                    "No hay canciones pendientes"
                )

            if voice.is_playing() or voice.is_paused():
                voice.stop()
            else:
                self.current.pop(guild_id, None)
                await self._iniciar_siguiente(guild_id)

        return {
            "mensaje": "Se solicitó pasar a la siguiente canción"
        }

    # --------------------------------------------------
    # DETENER Y VACIAR COLA
    # --------------------------------------------------

    async def detener_audio(self, guild_id):
        guild = self.get_guild(guild_id)

        if guild is None:
            raise ValueError("Servidor no encontrado")

        async with self._lock(guild_id):
            self.queues[guild_id].clear()
            self.current.pop(guild_id, None)
            self.playback_status[guild_id] = "detenida"

            voice = guild.voice_client

            if voice and (
                voice.is_playing() or voice.is_paused()
            ):
                voice.stop()

        return {
            "mensaje": "Reproducción detenida y cola vaciada",
            "estado": "detenida"
        }

    # --------------------------------------------------
    # PAUSAR
    # --------------------------------------------------

    async def pausar_audio(self, guild_id):
        guild = self.get_guild(guild_id)

        if guild and guild.voice_client:
            voice = guild.voice_client

            if voice.is_playing():
                voice.pause()
                self.playback_status[guild_id] = "pausada"

                return {
                    "mensaje": "Música pausada",
                    "estado": "pausada"
                }

        raise ValueError(
            "No hay música reproduciéndose"
        )

    # --------------------------------------------------
    # REANUDAR
    # --------------------------------------------------

    async def reanudar_audio(self, guild_id):
        guild = self.get_guild(guild_id)

        if guild and guild.voice_client:
            voice = guild.voice_client

            if voice.is_paused():
                voice.resume()
                self.playback_status[guild_id] = "reproduciendo"

                return {
                    "mensaje": "Música reanudada",
                    "estado": "reproduciendo"
                }

        raise ValueError(
            "No hay música pausada"
        )

    # --------------------------------------------------
    # SALIR DEL CANAL
    # --------------------------------------------------

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

        return {
            "mensaje": "Bot desconectado del canal de voz",
            "estado": "desconectado"
        }

    # --------------------------------------------------
    # ESTADO DEL BOT
    # --------------------------------------------------

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
            raise RuntimeError(
                "El bot no está iniciado"
            )

        return bot

    async def obtener_estado(self):
        estados = {}

        for bot in self.bots.values():
            if bot.is_ready():
                estados[str(bot.user.id)] = (
                    await bot.obtener_estado()
                )

        return estados

    async def cerrar_todos(self):
        for bot in list(self.bots.values()):
            await bot.close()

        self.bots.clear()


music_bots = MusicBotManager()
