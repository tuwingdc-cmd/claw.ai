FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (ADDED: ffmpeg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    git \
    libffi-dev \
    libsodium-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /tmp/tts /app/data

EXPOSE 3007

ENV PYTHONUNBUFFERED=1
ENV PORT=3007

CMD ["python", "main.py"]
