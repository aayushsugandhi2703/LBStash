# reports service image, built on the shared base (docker/base.Dockerfile).
ARG BASE_IMAGE=budget-base
FROM ${BASE_IMAGE}
COPY services/reports ./services/reports
RUN python -m compileall -q services/reports/src
ENV PYTHONPATH=/app/packages/bt/src:/app/services/reports/src PORT=3006 SERVICE_NAME=reports APP_ENV=production
USER app
EXPOSE 3006
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:3006/health', timeout=2)"
CMD ["python", "-m", "bt_reports.main"]
