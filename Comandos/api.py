
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from bot import music_bots


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await music_bots.cerrar_todos()


app = FastAPI(lifespan=lifespan)


class IniciarBotRequest(BaseModel):
    bot_id: str = Field(min_length=1)


class ReproducirRequest(BaseModel):
    bot_id: str = Field(min_length=1)
    guild_id: int
    channel_id: int
    query: str = Field(min_length=1, max_length=500)


class ServidorRequest(BaseModel):
    bot_id: str = Field(min_length=1)
    guild_id: int


async def ejecutar(funcion, *args):
    try:
        return await funcion(*args)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


def obtener_bot(bot_id):
    try:
        return music_bots.obtener_bot(bot_id)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error))


@app.get("/")
async def inicio():
    return {"mensaje": "API de música funcionando"}


@app.post("/bot/iniciar")
async def iniciar_bot(datos: IniciarBotRequest):
    return await ejecutar(music_bots.iniciar, datos.bot_id)


@app.get("/bot/estado")
async def estado_bots():
    return await music_bots.obtener_estado()


@app.post("/musica/reproducir")
async def reproducir(datos: ReproducirRequest):
    bot = obtener_bot(datos.bot_id)

    return await ejecutar(
        bot.agregar_a_cola,
        datos.guild_id,
        datos.channel_id,
        datos.query
    )


@app.post("/musica/cola")
async def ver_cola(datos: ServidorRequest):
    bot = obtener_bot(datos.bot_id)

    return await ejecutar(
        bot.obtener_cola,
        datos.guild_id
    )


@app.post("/musica/siguiente")
async def siguiente(datos: ServidorRequest):
    bot = obtener_bot(datos.bot_id)

    return await ejecutar(
        bot.siguiente,
        datos.guild_id
    )


@app.post("/musica/detener")
async def detener(datos: ServidorRequest):
    bot = obtener_bot(datos.bot_id)

    return await ejecutar(
        bot.detener_audio,
        datos.guild_id
    )


@app.post("/musica/pausar")
async def pausar(datos: ServidorRequest):
    bot = obtener_bot(datos.bot_id)

    return await ejecutar(
        bot.pausar_audio,
        datos.guild_id
    )


@app.post("/musica/reanudar")
async def reanudar(datos: ServidorRequest):
    bot = obtener_bot(datos.bot_id)

    return await ejecutar(
        bot.reanudar_audio,
        datos.guild_id
    )


@app.post("/musica/salir")
async def salir(datos: ServidorRequest):
    bot = obtener_bot(datos.bot_id)

    return await ejecutar(
        bot.salir_canal,
        datos.guild_id
    )


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000
    )
