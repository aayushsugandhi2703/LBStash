# recurring service image, built on the shared base (infra/docker/base.Dockerfile).
ARG BASE_IMAGE=lbstash-base
FROM ${BASE_IMAGE}
COPY services/recurring ./services/recurring
RUN python -m compileall -q services/recurring/src
ENV PYTHONPATH=/app/packages/lbstash/src:/app/services/recurring/src PORT=3005 SERVICE_NAME=recurring APP_ENV=production
USER app
EXPOSE 3005
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:3005/health', timeout=2)"
CMD ["python", "-m", "lbstash_recurring.main"]
