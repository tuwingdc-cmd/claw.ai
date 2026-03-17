FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    git \
    libffi-dev \
    libsodium-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Force install PyNaCl (jaminan)
RUN pip install --no-cache-dir PyNaCl>=1.5.0 && \
    python -c "import nacl; print('PyNaCl verified:', nacl.__version__)"

COPY . .

RUN mkdir -p /tmp/tts /app/data

EXPOSE 3007

ENV PYTHONUNBUFFERED=1
ENV PORT=3007

CMD ["python", "main.py"]
