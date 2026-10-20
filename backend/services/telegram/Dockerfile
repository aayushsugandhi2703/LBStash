# telegram service image, built on the shared base (infra/docker/base.Dockerfile).
ARG BASE_IMAGE=lbstash-base
FROM ${BASE_IMAGE}
COPY services/telegram ./services/telegram
RUN python -m compileall -q services/telegram/src
ENV PYTHONPATH=/app/packages/lbstash/src:/app/services/telegram/src PORT=3007 SERVICE_NAME=telegram APP_ENV=production
USER app
EXPOSE 3007
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:3007/health', timeout=2)"
CMD ["python", "-m", "lbstash_telegram.main"]
