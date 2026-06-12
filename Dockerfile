# TTB COLA Label Specialist POC — the offline-pinned build artifact (AR-1, AR-8).
# Story 1.1 bakes the base image, native OCR/image libs, and the pinned Python
# deps. Model weights, vendored USWDS, and seeded fixtures are layered in by
# later stories (Epic 1/2). Built on Docker Desktop, deployed to Railway Pro
# from THIS Dockerfile (not Nixpacks).
FROM python:3.13-slim

# Don't write .pyc, unbuffer stdout/stderr for clean container logs.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Native system deps (apt): Tesseract OCR engine + the shared libs OpenCV/Paddle
# need at import time (libGL, glib). Installed now so the image is reproducible
# and the runtime never reaches for a package mirror.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first for layer caching — only re-runs when the pins change.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Application code.
COPY pyproject.toml ./
COPY app ./app
COPY templates ./templates
COPY static ./static
COPY tests ./tests
COPY fixtures ./fixtures

EXPOSE 8000

# Liveness probe hits the pure in-memory route — no network, no DB.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).status==200 else 1)"

# Serve the app factory. Host 0.0.0.0 so the port is reachable from outside the
# container; startup performs zero outbound calls (proven by `--network none`).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
