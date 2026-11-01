FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl unzip && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL https://github.com/gulp79/rclone-extra/releases/download/v1.75.2-extra/rclone-linux-amd64.zip -o /tmp/rclone.zip \
 && echo "78855325a2a8d83b3feee3a8363d32e1211babbf4cda6356fa8ca5f472075062  /tmp/rclone.zip" | sha256sum -c - \
 && unzip -q /tmp/rclone.zip -d /tmp/rclone-extra \
 && find /tmp/rclone-extra -type f -name rclone -exec install -m 755 {} /usr/local/bin/rclone \; \
 && rm -rf /tmp/rclone.zip /tmp/rclone-extra \
 && rclone help backends | grep -qi terabox
RUN python -m pip install --no-cache-dir fastapi==0.115.12 uvicorn==0.35.0
WORKDIR /app
COPY apps/demand-research/gateway.py /app/gateway.py
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 10000
CMD ["sh","-c","exec uvicorn gateway:app --host 0.0.0.0 --port ${PORT:-10000}"]
