# TTB COLA Label Specialist POC — the offline-pinned build artifact (AR-1, AR-8).
# Story 1.1 bakes the base image, native OCR/image libs, and the pinned Python
# deps. Model weights, vendored USWDS, and seeded fixtures are layered in by
# later stories (Epic 1/2). Built on Docker Desktop, deployed to Railway Pro
# from THIS Dockerfile (not Nixpacks).
FROM python:3.13-slim

# Don't write .pyc, unbuffer stdout/stderr for clean container logs.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # PaddleOCR/PaddleX resolve model weights from this cache dir. The build-time
    # warmup below populates it; at RUNTIME the weights are already on disk so
    # PaddleOCR loads them locally and makes ZERO network calls (Story 2.4 AC4 —
    # the OCR job is classified `none`; proven by `docker run --network none`).
    PADDLE_PDX_CACHE_HOME=/app/models/paddlex \
    # The OCR adapter (app/adapters/ocr/paddleocr.py) reads this to explicitly pin
    # detection/recognition weights (det/ + rec/ subdirs) when that baked layout is
    # present; until a build host bakes that layout it falls back to the warmed
    # PADDLE_PDX_CACHE_HOME above — both are offline (AC4). Build-host TODO: bake the
    # det/rec layout under this dir to fully activate explicit pinning.
    PADDLEOCR_MODEL_DIR=/app/models/paddlex \
    # PaddleOCR/PaddleX probe "the model hosters" for connectivity even when weights
    # are already cached. Disable that probe so neither the build nor the cached-weights
    # runtime makes an outbound call — required for a clean `docker run --network none`
    # boot (AC4 / NFR-2); with weights baked there is nothing to fetch anyway.
    PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True

# Native system deps (apt): Tesseract OCR engine (the `tesseract-ocr` package bundles
# the English `eng` language data pytesseract needs) + the shared libs OpenCV/Paddle
# need at import time (libGL, glib). Installed now so the image is reproducible and the
# runtime never reaches for a package mirror.
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

# Bake the pinned PP-OCRv5 weights into the image at BUILD time (network is allowed
# during build, never at runtime — AR-8/D7). Instantiating PaddleOCR once downloads
# the detection + recognition models into $PADDLE_PDX_CACHE_HOME; that layer is then
# part of the image, so the runtime container loads weights from disk with no egress.
# If this step fails the build fails loudly — we never ship an image that would try to
# download weights at runtime (which `--network none` would turn into a hard error).
RUN python -c "from paddleocr import PaddleOCR; PaddleOCR(lang='en', device='cpu')" \
    && python -c "import os; assert os.path.isdir(os.environ['PADDLE_PDX_CACHE_HOME']), 'PaddleOCR weights were not baked'"

# Application code.
COPY pyproject.toml ./
COPY app ./app
COPY templates ./templates
COPY static ./static
COPY tests ./tests
COPY fixtures ./fixtures

EXPOSE 8000

# Liveness probe hits the pure in-memory route — no network, no DB. Reads $PORT
# (Railway injects it; defaults to 8000 for local/compose) so the probe targets
# the same port the server binds — see railway.toml's $PORT reconciliation. Use
# `or '8000'` (not get's default) so an empty `PORT=""` also falls back — the
# default only applies when the var is *absent*, and an empty value would build a
# malformed `http://127.0.0.1:/healthz` and false-fail an otherwise healthy boot.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import os,urllib.request,sys; p=os.environ.get('PORT') or '8000'; sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{p}/healthz', timeout=2).status==200 else 1)"

# Serve the app factory. Host 0.0.0.0 so the port is reachable from outside the
# container; startup performs zero outbound calls (proven by `--network none`).
# Local/compose default is 8000; on Railway the railway.toml startCommand
# overrides this CMD to bind the injected $PORT.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
