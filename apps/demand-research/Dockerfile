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
COPY apps/demand-research/target_archive_api.py /app/target_archive_api.py
COPY apps/demand-research/target_account_archive.py /app/target_account_archive.py
COPY apps/demand-research/demand_archive.py /app/demand_archive.py
COPY apps/demand-research/social_sources.py /app/social_sources.py
COPY apps/demand-research/account_index.py /app/account_index.py
COPY apps/demand-research/account_groups.py /app/account_groups.py
COPY apps/demand-research/account_group_client.js /app/account_group_client.js
COPY apps/demand-research/account_index_sources.py /app/account_index_sources.py
COPY apps/demand-research/account_auto_analysis.js /app/account_auto_analysis.js
COPY apps/demand-research/account_index_client.js /app/account_index_client.js
COPY apps/demand-research/account_watch.js /app/account_watch.js
COPY apps/demand-research/free_discovery.js /app/free_discovery.js
COPY apps/demand-research/post_activity_ranking.js /app/post_activity_ranking.js
COPY apps/demand-research/target_archive_client.js /app/target_archive_client.js
COPY apps/demand-research/assets /app/assets
COPY apps/demand-research/index.html /app/index.html
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 10000
CMD ["sh","-c","exec uvicorn gateway:app --host 0.0.0.0 --port ${PORT:-10000}"]
