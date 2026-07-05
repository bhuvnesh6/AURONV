# ── AURON — Production Dockerfile ──────────────────────────────────────────
# Base: slim Python 3.11 (smaller image, faster builds)
FROM python:3.11-slim

# Metadata
LABEL maintainer="auron@phishnix.site"
LABEL description="AURON Fitness Accountability Platform"

# ── System deps ─────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ────────────────────────────────────────────────────────
WORKDIR /app

# ── Python deps (cached layer — copy requirements first) ────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── App source ───────────────────────────────────────────────────────────────
COPY . .

# ── Non-root user for security ───────────────────────────────────────────────
RUN adduser --disabled-password --gecos "" auronuser \
    && chown -R auronuser:auronuser /app
USER auronuser

# ── Port ─────────────────────────────────────────────────────────────────────
EXPOSE 5051

# ── Health check ─────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5051/')" || exit 1

# ── Start with Gunicorn ───────────────────────────────────────────────────────
# 4 workers x 2 threads = handles ~8 concurrent requests
CMD ["gunicorn", "--bind", "0.0.0.0:5051", "--workers", "4", "--threads", "2", "--worker-class", "gthread", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "--log-level", "info", "app:create_app()"]