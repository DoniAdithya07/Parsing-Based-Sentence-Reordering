# syntax=docker/dockerfile:1.7

FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VENV_PATH=/opt/venv \
    NLTK_DATA=/app/.nltk_data

WORKDIR /app

# Build deps for any package that may need compilation (spaCy stack / blis fallback).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv $VENV_PATH
ENV PATH="$VENV_PATH/bin:$PATH"

COPY requirements.txt .
RUN python -m pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt \
    && python -m spacy download en_core_web_sm

# Preload NLTK resources required for Reuters sample endpoint on Render.
RUN mkdir -p /app/.nltk_data \
    && python -c "import nltk; nltk.download('reuters', download_dir='/app/.nltk_data', quiet=True); nltk.download('punkt', download_dir='/app/.nltk_data', quiet=True)"


FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VENV_PATH=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    NLTK_DATA=/app/.nltk_data \
    PORT=10000

WORKDIR /app

# Optional but recommended: run as non-root.
RUN useradd -m -u 10001 appuser

# Copy prebuilt Python environment and NLTK corpus cache from builder.
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app/.nltk_data /app/.nltk_data

# Copy application source.
COPY . .

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 10000

# Render provides $PORT at runtime; default kept at 10000.
CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:${PORT:-10000} --workers 2 --threads 4 --timeout 120"]
