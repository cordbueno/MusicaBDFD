


import asyncio

import logging
import shlex

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
