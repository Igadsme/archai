# API and worker image (the worker runs the same image with `python -m archai_api.worker`).
FROM python:3.11-slim

# CPU-only PyTorch wheels keep the image ~1 GB instead of pulling multi-GB CUDA wheels.
# Override with --build-arg TORCH_INDEX_URL=https://download.pytorch.org/whl/cu124 for GPU hosts.
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    ARCHAI_RESULTS_DIR=/opt/archai/research/results

WORKDIR /opt/archai
RUN groupadd --system --gid 10001 archai \
    && useradd --system --uid 10001 --gid archai --home-dir /opt/archai --shell /usr/sbin/nologin archai \
    && mkdir -p /var/lib/archai \
    && chown archai:archai /var/lib/archai

COPY pyproject.toml README.md alembic.ini ./
COPY packages ./packages
COPY apps/api ./apps/api
RUN pip install --extra-index-url "${TORCH_INDEX_URL}" '.[ml,platform,benchmark]'
COPY scripts ./scripts
COPY research ./research
COPY datasets/fixtures ./datasets/fixtures

USER 10001
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen(f\"http://127.0.0.1:{os.getenv('PORT', '8000')}/health\", timeout=4)"]
# FORWARDED_ALLOW_IPS must list the reverse proxy's address so per-client rate limits see real client IPs.
CMD ["sh", "-c", "exec uvicorn archai_api.main:app --host 0.0.0.0 --port \"${PORT:-8000}\" --proxy-headers --forwarded-allow-ips \"${FORWARDED_ALLOW_IPS:-127.0.0.1}\" --workers \"${WEB_CONCURRENCY:-1}\""]
