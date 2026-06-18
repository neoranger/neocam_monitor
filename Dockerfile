FROM python:3.10-slim

WORKDIR /app

# Instalar dependencias del sistema necesarias
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgstrtspserver-1.0-0 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Asegurar directorios de base de datos
RUN mkdir -p /app/instance && chmod 777 /app/instance

EXPOSE 5000

ENV PYTHONUNBUFFERED=1

CMD ["python", "app.py"]
