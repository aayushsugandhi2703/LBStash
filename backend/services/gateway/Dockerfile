# gateway service image, built on the shared base (infra/docker/base.Dockerfile).
ARG BASE_IMAGE=lbstash-base
FROM ${BASE_IMAGE}
COPY services/gateway ./services/gateway
RUN python -m compileall -q services/gateway/src
ENV PYTHONPATH=/app/packages/lbstash/src:/app/services/gateway/src PORT=3000 SERVICE_NAME=gateway APP_ENV=production
USER app
EXPOSE 3000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:3000/health', timeout=2)"
CMD ["python", "-m", "lbstash_gateway.main"]
