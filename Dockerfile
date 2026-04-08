# syntax=docker/dockerfile:1.7

FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VENV_PATH=/opt/venv

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


FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VENV_PATH=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PORT=10000

WORKDIR /app

# Optional but recommended: run as non-root.
RUN useradd -m -u 10001 appuser

# Copy prebuilt Python environment from builder (contains spaCy + model).
COPY --from=builder /opt/venv /opt/venv

# Copy application source.
COPY . .

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 10000

# Render provides $PORT at runtime; default kept at 10000.
CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:${PORT:-10000} --workers 2 --threads 4 --timeout 120"]
