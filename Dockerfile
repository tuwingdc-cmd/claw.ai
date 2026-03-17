FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all source code
COPY . .

# Create directories
RUN mkdir -p /tmp/tts /app/data

# Expose port for health check
EXPOSE 3007

# Set environment
ENV PYTHONUNBUFFERED=1
ENV PORT=3007

# Run bot
CMD ["python", "main.py"]
