# planning service image, built on the shared base (infra/docker/base.Dockerfile).
ARG BASE_IMAGE=lbstash-base
FROM ${BASE_IMAGE}
COPY services/planning ./services/planning
RUN python -m compileall -q services/planning/src
ENV PYTHONPATH=/app/packages/lbstash/src:/app/services/planning/src PORT=3004 SERVICE_NAME=planning APP_ENV=production
USER app
EXPOSE 3004
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:3004/health', timeout=2)"
CMD ["python", "-m", "lbstash_planning.main"]
