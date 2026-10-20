# syntax=docker/dockerfile:1.7-labs
# Shared Python image for every backend service (db-init uses it too).
# Build from the repo root: docker build -f infra/docker/base.Dockerfile -t lbstash-base backend

# 1. builder: install the dependencies, then trim them
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /usr/local/bin/uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_DEV=1 UV_NO_CACHE=1
WORKDIR /app
# only the dependency lists, so this step is cached until they change
COPY --parents pyproject.toml uv.lock packages/lbstash/pyproject.toml services/*/pyproject.toml ./
RUN uv sync --frozen --all-packages --no-install-workspace
# remove unused extras and build-only files, strip debug info (speed is the same)
RUN set -eux; \
    SP=/opt/venv/lib/python3.12/site-packages; \
    rm -rf "$SP"/yaml "$SP"/_yaml "$SP"/websockets "$SP"/watchfiles "$SP"/dotenv \
           "$SP"/pyyaml-*.dist-info "$SP"/websockets-*.dist-info "$SP"/watchfiles-*.dist-info "$SP"/python_dotenv-*.dist-info; \
    find /opt/venv \( -name '*.c' -o -name '*.pyx' -o -name '*.pxd' -o -name '*.h' -o -name '*.pyi' \) -delete; \
    apt-get update; apt-get install -y --no-install-recommends binutils; \
    find "$SP"/uvloop "$SP"/cryptography "$SP"/httptools "$SP"/cbor2 -name '*.so' -exec strip --strip-unneeded {} +; \
    rm -rf /var/lib/apt/lists/*

# 2. rootfs: the stock Python image without what we never use
FROM python:3.12-slim AS rootfs
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH=/opt/venv/bin:$PATH PYTHONPATH=/app/packages/lbstash/src
# remove pip, unused Python tools, C headers, charset plugins and caches
RUN set -eux; \
    cd /usr/local/lib/python3.12; \
    rm -rf ensurepip idlelib tkinter lib2to3 pydoc_data turtledemo turtle.py config-3.12-*-linux-gnu \
           site-packages/pip site-packages/pip-*.dist-info lib-dynload/_tkinter*; \
    rm -rf /usr/local/include /usr/local/bin/pip* /usr/local/bin/idle* /usr/local/bin/2to3* /usr/local/bin/pydoc* /usr/local/bin/python*-config; \
    rm -f /usr/lib/*-linux-gnu/gconv/*.so; \
    rm -rf /var/cache/* /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY packages/lbstash ./packages/lbstash
RUN useradd --system --uid 10001 --no-create-home app && python -m compileall -q packages/lbstash/src

# 3. final: one flat layer, so the removed files really free space
FROM scratch
COPY --from=rootfs / /
# a flat image has no settings, so set them again
ENV LANG=C.UTF-8 PATH=/opt/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app/packages/lbstash/src
WORKDIR /app
CMD ["python3"]
