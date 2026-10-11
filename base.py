
import discord
from discord.ext import commands

# =========================
# CONFIGURACIÓN
# =========================



# Aquí colocarás tu URL directa al archivo MP3


intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)


# =========================
# CUANDO EL BOT SE CONECTA
# =========================

@bot.event
async def on_ready():
    print(f"Bot conectado como: {bot.user}")


# =========================
# UNIRSE Y REPRODUCIR
# =========================






@bot.command()
async def reproducir(ctx , query: str):
    if not ctx.author.voice:
        await ctx.send("Debes estar en un canal de voz primero.")
        return

    from Comandos.youtube import youtube_search
    from Comandos.buscar import get_youtube_audio_url
    n = youtube_search(query)
    
    h = get_youtube_audio_url(n)

    canal = ctx.author.voice.channel
    voice_client = ctx.voice_client

    try:
        # Unirse al canal o cambiarse al canal del usuario
        if voice_client is None:
            voice_client = await canal.connect()
        elif voice_client.channel != canal:
            await voice_client.move_to(canal)

        # Detener la reproducción anterior
        if voice_client.is_playing():
            voice_client.stop()

        # Configurar FFmpeg
        fuente = discord.FFmpegPCMAudio(
            h,
            before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            options="-vn"
        )

        # Reproducir el MP3
        voice_client.play(
            fuente,
            after=lambda error: print(
                f"Error de reproducción: {error}"
            ) if error else None
        )

        await ctx.send("🎵 Reproduciendo música en el canal de voz.")

    except Exception as error:
        await ctx.send(f"No se pudo reproducir el audio: {error}")
        print(f"Error: {error}")


# =========================
# DETENER LA MÚSICA
# =========================

@bot.command()
async def detener(ctx):
    voice_client = ctx.voice_client

    if voice_client and voice_client.is_playing():
        voice_client.stop()
        await ctx.send("⏹️ Música detenida.")
    else:
        await ctx.send("No hay música reproduciéndose.")


# =========================
# SALIR DEL CANAL
# =========================

@bot.command()
async def salir(ctx):
    voice_client = ctx.voice_client

    if voice_client:
        await voice_client.disconnect()
        await ctx.send("👋 He salido del canal de voz.")
    else:
        await ctx.send("No estoy conectado a un canal de voz.")


# =========================
# INICIAR BOT
# =========================

bot.run(TOKEN)
