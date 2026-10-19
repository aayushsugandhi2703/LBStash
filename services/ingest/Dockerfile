# ingest service image, built on the shared base (docker/base.Dockerfile).
ARG BASE_IMAGE=budget-base
FROM ${BASE_IMAGE}
COPY services/ingest ./services/ingest
RUN python -m compileall -q services/ingest/src
ENV PYTHONPATH=/app/packages/bt/src:/app/services/ingest/src PORT=3003 SERVICE_NAME=ingest APP_ENV=production
USER app
EXPOSE 3003
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:3003/health', timeout=2)"
CMD ["python", "-m", "bt_ingest.main"]
