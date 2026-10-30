FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl unzip ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
ARG RCLONE_EXTRA_URL=https://github.com/gulp79/rclone-extra/releases/download/v1.75.2-extra/rclone-linux-amd64.zip
ARG RCLONE_EXTRA_SHA256=78855325a2a8d83b3feee3a8363d32e1211babbf4cda6356fa8ca5f472075062
RUN curl -fsSL "$RCLONE_EXTRA_URL" -o /tmp/rclone.zip \
  && echo "$RCLONE_EXTRA_SHA256  /tmp/rclone.zip" | sha256sum -c - \
  && mkdir -p /tmp/rclone-unpack \
  && unzip -q /tmp/rclone.zip -d /tmp/rclone-unpack \
  && find /tmp/rclone-unpack -type f -name rclone -exec install -m 755 {} /usr/local/bin/rclone \; \
  && rclone version \
  && rm -rf /tmp/rclone*
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py portal.py media_cache.py ./
ENV PYTHONUNBUFFERED=1
EXPOSE 10000
CMD ["sh","-c","exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}"]
