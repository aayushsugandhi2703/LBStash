# syntax=docker/dockerfile:1.7-labs
# Shared base for every Python service: Python 3.12, all backend dependencies in one venv, the `lbstash` library. No uv at runtime.
# Services add only their own source. The one-shot `db-init` job also runs this image (`python -m lbstash.db.init`).
# Build: docker build -f docker/base.Dockerfile -t lbstash-base .

FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /usr/local/bin/uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_DEV=1 UV_NO_CACHE=1
WORKDIR /app
# Manifests only, so this layer is cached until a dependency changes.
COPY --parents pyproject.toml uv.lock packages/lbstash/pyproject.toml services/*/pyproject.toml ./
RUN uv sync --frozen --all-packages --no-install-workspace

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH=/opt/venv/bin:$PATH PYTHONPATH=/app/packages/lbstash/src
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY packages/lbstash ./packages/lbstash
RUN useradd --system --uid 10001 --no-create-home app && python -m compileall -q packages/lbstash/src
