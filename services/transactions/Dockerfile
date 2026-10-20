# transactions service image, built on the shared base (docker/base.Dockerfile).
ARG BASE_IMAGE=lbstash-base
FROM ${BASE_IMAGE}
COPY services/transactions ./services/transactions
RUN python -m compileall -q services/transactions/src
ENV PYTHONPATH=/app/packages/lbstash/src:/app/services/transactions/src PORT=3002 SERVICE_NAME=transactions APP_ENV=production
USER app
EXPOSE 3002
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:3002/health', timeout=2)"
CMD ["python", "-m", "lbstash_transactions.main"]
