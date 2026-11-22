# syntax=docker/dockerfile:1
# Multi-stage, digest-pinned, non-root (docs/engineering-practices.md §5).
FROM ghcr.io/astral-sh/uv:0.9@sha256:538e0b39736e7feae937a65983e49d2ab75e1559d35041f9878b7b7e51de91e4 AS uv

FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df AS build
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-group data --no-install-project
COPY src ./src
COPY config ./config
RUN uv sync --frozen --no-dev --no-group data

FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df AS runtime
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-ara curl \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 10001 app
WORKDIR /app
COPY --from=build --chown=app:app /app /app
ENV PATH="/app/.venv/bin:$PATH" DATA_DIR=/data PYTHONUNBUFFERED=1
RUN mkdir -p /data && chown app:app /data
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1
CMD ["uvicorn", "licence_kyb.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
