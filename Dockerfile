FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    git \
    libffi-dev \
    libsodium-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy dan install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Verify critical libraries
RUN python3 -c "
import sys
try:
    import discord
    print(f'✅ discord.py: {discord.__version__}', file=sys.stderr)
    
    import nacl
    print(f'✅ PyNaCl: {nacl.__version__}', file=sys.stderr)
    
    from discord import opus
    if opus.is_loaded():
        print('✅ Opus: loaded', file=sys.stderr)
    else:
        print('⚠️  Opus: not loaded (may not affect Wavelink)', file=sys.stderr)
    
    import wavelink
    print(f'✅ Wavelink: {wavelink.__version__}', file=sys.stderr)
    
except Exception as e:
    print(f'❌ Verification failed: {e}', file=sys.stderr)
    sys.exit(1)
"

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /tmp/tts /app/data

EXPOSE 3007

ENV PYTHONUNBUFFERED=1
ENV PORT=3007

CMD ["python3", "main.py"]
