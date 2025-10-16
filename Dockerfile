FROM python:3.12-slim

# Install ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first (layer caching)
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

# Security: you should override FLASK_SECRET_KEY in the platform settings
ENV PORT=8000 PYTHONUNBUFFERED=1

# Gunicorn (app factory)
CMD ["gunicorn", "app:create_app()", "-b", "0.0.0.0:8000", "--workers", "2", "--threads", "4", "--timeout", "180"]