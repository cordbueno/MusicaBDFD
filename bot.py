import asyncio
import logging
import shlex
from collections import defaultdict, deque
import discord
from discord.ext import commands
from Comandos.youtube import youtube_search
from Comandos.buscar import get_youtube_audio_info
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(name)s | %(message)s')
logger = logging.getLogger('music_bot')

class MusicBot(commands.Bot):

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        super().__init__(command_prefix='!', intents=intents)
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
            return {'mensaje': 'El bot ya está iniciado', 'bot_id': str(self.user.id)}
        await self.login(token)
        self._connect_task = asyncio.create_task(self.connect(reconnect=True))
        try:
            await asyncio.wait_for(self.wait_until_ready(), timeout=60)
        except asyncio.TimeoutError:
            self._connect_task.cancel()
            await self.close()
            raise RuntimeError('El bot no pudo conectarse a Discord a tiempo')
        return {'mensaje': 'Bot iniciado correctamente', 'bot_id': str(self.user.id), 'nombre': str(self.user)}

    def _extraer_url(self, resultado):
        if isinstance(resultado, str):
            if resultado.startswith(('https://', 'http://')):
                return resultado
            raise ValueError('La búsqueda no devolvió una URL válida')
        if isinstance(resultado, dict):
            for clave in ('webpage_url', 'url', 'video_url', 'link'):
                valor = resultado.get(clave)
                if isinstance(valor, str) and valor.startswith('http'):
                    return valor
            for clave in ('videos', 'results', 'items'):
                lista = resultado.get(clave)
                if lista:
                    return self._extraer_url(lista[0])
        if isinstance(resultado, (list, tuple)) and resultado:
            return self._extraer_url(resultado[0])
        raise ValueError('No se pudo obtener la URL del video de YouTube')

    def _extraer_titulo(self, resultado, query):
        if isinstance(resultado, dict):
            return resultado.get('title') or resultado.get('titulo') or query
        if isinstance(resultado, (list, tuple)) and resultado:
            return self._extraer_titulo(resultado[0], query)
        return query

    async def agregar_a_cola(self, guild_id, channel_id, query):
        guild = self.get_guild(guild_id)
        if guild is None:
            raise ValueError('El bot no está en el servidor indicado')
        canal = guild.get_channel(channel_id)
        if not isinstance(canal, (discord.VoiceChannel, discord.StageChannel)):
            raise ValueError('El canal de voz no es válido')
        resultado = await asyncio.to_thread(youtube_search, query)
        url = self._extraer_url(resultado)
        titulo = self._extraer_titulo(resultado, query)
        elemento = {'titulo': titulo, 'url': url, 'resultado': resultado, 'query': query, '_intentos': 0}
        async with self._lock(guild_id):
            voice = guild.voice_client
            if voice is None:
                voice = await canal.connect()
            elif voice.channel.id != channel_id:
                await voice.move_to(canal)
            self.queues[guild_id].append(elemento)
            posicion = len(self.queues[guild_id])
            if voice.is_playing() or voice.is_paused():
                estado = 'pendiente'
            else:
                estado = 'pendiente'
            self.playback_status[guild_id] = estado
            if not voice.is_playing() and (not voice.is_paused()):
                await self._iniciar_siguiente(guild_id)
        return {'mensaje': 'Se agregó la música a la cola', 'cancion': titulo, 'url': url, 'posicion': posicion, 'estado': self.playback_status.get(guild_id, 'pendiente')}

    async def reproducir_audio(self, guild_id, channel_id, query):
        return await self.agregar_a_cola(guild_id, channel_id, query)

    async def _iniciar_siguiente(self, guild_id):
        guild = self.get_guild(guild_id)
        if guild is None:
            return
        voice = guild.voice_client
        if voice is None or not voice.is_connected():
            self.playback_status[guild_id] = 'desconectado'
            return
        if voice.is_playing() or voice.is_paused():
            return
        while self.queues[guild_id]:
            elemento = self.queues[guild_id].popleft()
            try:
                resultado = await asyncio.to_thread(youtube_search, elemento['query'])
                url_video = self._extraer_url(resultado)
                audio_info = await asyncio.to_thread(get_youtube_audio_info, url_video)
                if not audio_info:
                    raise RuntimeError('No se obtuvo una URL de audio')
                url_audio = audio_info['url']
                headers = audio_info.get('headers', {})
                headers_text = ''.join((f'{nombre}: {valor}\r\n' for nombre, valor in headers.items()))
                headers_option = f' -headers {shlex.quote(headers_text)}' if headers_text else ''
                fuente = discord.FFmpegPCMAudio(url_audio, before_options='-nostdin -reconnect 1 -reconnect_streamed 1 -reconnect_at_eof 1 -reconnect_delay_max 10 -rw_timeout 15000000' + headers_option, options='-vn -loglevel warning')
                loop = asyncio.get_running_loop()
                self.current[guild_id] = elemento
                self.playback_status[guild_id] = 'reproduciendo'

                def al_terminar(error):
                    if error:
                        logger.error("Error durante '%s': %s", elemento['titulo'], error)
