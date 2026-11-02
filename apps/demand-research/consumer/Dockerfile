FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN python -m pip install --no-cache-dir fastapi==0.115.12 uvicorn==0.35.0
COPY apps/demand-research/consumer_dedup.py /app/consumer_dedup.py
COPY apps/demand-research/consumer_report.py /app/consumer_report.py
COPY apps/demand-research/consumer_report_api.py /app/consumer_report_api.py
COPY apps/demand-research/consumer/editorial-report.json /app/consumer/editorial-report.json
RUN useradd --create-home --uid 10001 api && chown -R api:api /app
USER api
EXPOSE 10000
CMD ["sh", "-c", "exec uvicorn consumer_report_api:app --host 0.0.0.0 --port ${PORT:-10000}"]
