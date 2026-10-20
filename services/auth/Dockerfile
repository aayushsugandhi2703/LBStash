# auth service image, built on the shared base (docker/base.Dockerfile).
ARG BASE_IMAGE=lbstash-base
FROM ${BASE_IMAGE}
COPY services/auth ./services/auth
RUN python -m compileall -q services/auth/src
ENV PYTHONPATH=/app/packages/lbstash/src:/app/services/auth/src PORT=3001 SERVICE_NAME=auth APP_ENV=production
USER app
EXPOSE 3001
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:3001/health', timeout=2)"
CMD ["python", "-m", "lbstash_auth.main"]
