FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY deploy/backend/requirements.txt deploy/backend/requirements.lock /tmp/requirements/
RUN pip install --no-cache-dir -r /tmp/requirements/requirements.txt && useradd --uid 10001 --create-home goob
COPY operations/api_v1 /app/operations/api_v1
COPY operations/domain /app/operations/domain
COPY operations/persistence /app/operations/persistence
COPY operations/integrations /app/operations/integrations
COPY operations/migrations /app/operations/migrations
COPY alembic-backend.ini /app/alembic-backend.ini
COPY scripts/bootstrap_backend.py /app/scripts/bootstrap_backend.py
USER goob
EXPOSE 8090
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/health/ready', timeout=3)"
CMD ["uvicorn", "operations.api_v1.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8090", "--workers", "2", "--no-access-log", "--limit-concurrency", "50"]
