
FROM python:3.12-slim

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Instalar Deno
ENV DENO_INSTALL=/usr/local

RUN curl -fsSL https://deno.land/install.sh | sh \
    && ln -sf /usr/local/bin/deno /usr/local/bin/deno

# Configurar directorio del proyecto
WORKDIR /app

# Instalar dependencias Python
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir "yt-dlp[default]" \
    && pip install --no-cache-dir -r requirements.txt

# Copiar archivos del proyecto
COPY . .

# Iniciar FastAPI
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
