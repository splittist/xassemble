# syntax=docker/dockerfile:1.7

FROM node:24-bookworm-slim AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM ghcr.io/astral-sh/uv:0.9.11 AS uv

FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    XASSEMBLE_DB=/data/xassemble.sqlite3 \
    XASSEMBLE_FRONTEND_DIST=/app/frontend/dist

COPY --from=uv /uv /uvx /bin/
WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src/ ./src/
RUN uv sync --frozen --no-dev
COPY --from=frontend-build /build/frontend/dist ./frontend/dist

RUN groupadd --system --gid 10001 xassemble \
    && useradd --system --uid 10001 --gid xassemble --home-dir /app xassemble \
    && mkdir -p /data \
    && chown xassemble:xassemble /data

ENV PATH="/app/.venv/bin:$PATH"
USER xassemble
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()"]
CMD ["uvicorn", "xassemble.app:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
