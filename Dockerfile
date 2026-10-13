
FROM python:3.12-slim

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    curl \
    unzip \
    ca-certificates \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Instalar Deno
ENV DENO_INSTALL=/root/.deno

RUN curl -fsSL https://deno.land/install.sh | sh

ENV PATH="/root/.deno/bin:${PATH}"

# Directorio de trabajo
WORKDIR /app

# Instalar dependencias de Python
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir "yt-dlp[default]" \
    && pip install --no-cache-dir -r requirements.txt

# Copiar el proyecto
COPY . .

# Comprobar la instalación de Deno
RUN deno --version

# Iniciar FastAPI desde api.py
CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}"]

