# syntax=docker/dockerfile:1.6
# =====================================================
# Wissenswerkstatt - Multi-Stage Build
# =====================================================

# --- Stage 1: Builder --------------------------------------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY app/requirements.txt ./requirements.txt
RUN pip install --user -r requirements.txt

# --- Stage 2: Runtime --------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/home/app/.local/bin:$PATH \
    APP_HOME=/app \
    DATA_DIR=/app/data

# Nicht als root laufen
RUN groupadd --system app \
    && useradd --system --gid app --home /home/app --create-home --shell /bin/false app \
    && mkdir -p /app/data \
    && chown -R app:app /app /home/app

WORKDIR /app

COPY --from=builder /root/.local /home/app/.local
COPY --chown=app:app app/ /app/

USER app

EXPOSE 8080

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; \
sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=3).status == 200 else sys.exit(1)"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips=*"]
