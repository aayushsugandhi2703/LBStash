# syntax=docker/dockerfile:1.7-labs
# Shared base image: Python 3.12, uv, the locked dependencies and the `bt` library.
# Every service image starts `FROM budget-base`; the one-shot `db-init` job runs it too (`python -m bt.db.init`).
# Build: docker build -f docker/base.Dockerfile -t budget-base .
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /usr/local/bin/uv
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_DEV=1 \
    PATH=/opt/venv/bin:$PATH
WORKDIR /app

# Manifests of every workspace member first: the lockfile resolves the whole workspace, and this layer is cached
# until a dependency changes.
COPY --parents pyproject.toml uv.lock packages/bt/pyproject.toml services/*/pyproject.toml ./
RUN uv sync --frozen --package bt --no-install-workspace

COPY packages/bt ./packages/bt
RUN uv sync --frozen --package bt \
 && useradd --system --uid 10001 --no-create-home app
