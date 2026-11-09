FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl unzip && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL https://github.com/gulp79/rclone-extra/releases/download/v1.75.2-extra/rclone-linux-amd64.zip -o /tmp/rclone.zip \
 && echo "78855325a2a8d83b3feee3a8363d32e1211babbf4cda6356fa8ca5f472075062  /tmp/rclone.zip" | sha256sum -c - \
 && unzip -q /tmp/rclone.zip -d /tmp/rclone-extra \
 && find /tmp/rclone-extra -type f -name rclone -exec install -m 755 {} /usr/local/bin/rclone \; \
 && rm -rf /tmp/rclone.zip /tmp/rclone-extra \
 && rclone help backends | grep -qi terabox
RUN python -m pip install --no-cache-dir fastapi==0.115.12 uvicorn==0.35.0 PyJWT==2.10.1 cryptography==46.0.4
WORKDIR /app
COPY apps/demand-research/gateway.py /app/gateway.py
COPY apps/demand-research/sealed_credentials.py /app/sealed_credentials.py
COPY apps/demand-research/target_archive_api.py /app/target_archive_api.py
COPY apps/demand-research/backup_queue.py /app/backup_queue.py
COPY apps/demand-research/github_temp_bundle.py /app/github_temp_bundle.py
COPY apps/demand-research/target_account_archive.py /app/target_account_archive.py
COPY apps/demand-research/target_account_enrichment.py /app/target_account_enrichment.py
COPY apps/demand-research/target_account_viewer.py /app/target_account_viewer.py
COPY apps/demand-research/verified_bundle_reader.py /app/verified_bundle_reader.py
COPY apps/demand-research/account_archive_view.html /app/account_archive_view.html
COPY apps/demand-research/account_archive_view.js /app/account_archive_view.js
COPY apps/demand-research/account_archive_view.css /app/account_archive_view.css
COPY apps/demand-research/auto_archive_view.html /app/auto_archive_view.html
COPY apps/demand-research/auto_archive_view.js /app/auto_archive_view.js
COPY apps/demand-research/auto_archive_view.css /app/auto_archive_view.css
COPY apps/demand-research/demand_archive.py /app/demand_archive.py
COPY apps/demand-research/social_sources.py /app/social_sources.py
COPY apps/demand-research/account_index.py /app/account_index.py
COPY apps/demand-research/account_index_job.py /app/account_index_job.py
COPY apps/demand-research/account_index_bootstrap.py /app/account_index_bootstrap.py
# This is PUBLIC AES-256-GCM ciphertext, not a secret or account data in
# plaintext. Pin immutable asset SHA at BUILD time; no external CDN is needed
# for the free Render instance to rehydrate after it sleeps.
RUN curl --fail --silent --show-error --location --retry 6 --retry-all-errors \
    --retry-delay 3 --connect-timeout 20 --max-time 100 \
    https://github.com/koith/browser-app-lab/releases/download/intersection-index-boot-20261109/index.enc \
    -o /app/account-index-boot.enc \
 && echo 'a3aafe2a9dfe1cf4e02488c8039a52723e925b1719310faf91fcb76e3e998650  /app/account-index-boot.enc' | sha256sum -c - \
 && chmod 0444 /app/account-index-boot.enc
COPY apps/demand-research/account_groups.py /app/account_groups.py
COPY apps/demand-research/account_group_client.js /app/account_group_client.js
COPY apps/demand-research/account_index_sources.py /app/account_index_sources.py
COPY apps/demand-research/account_auto_analysis.js /app/account_auto_analysis.js
COPY apps/demand-research/account_index_client.js /app/account_index_client.js
COPY apps/demand-research/account_watch.js /app/account_watch.js
COPY apps/demand-research/archive_tab.js /app/archive_tab.js
COPY apps/demand-research/free_discovery.js /app/free_discovery.js
COPY apps/demand-research/post_activity_ranking.js /app/post_activity_ranking.js
COPY apps/demand-research/public_video_trends.js /app/public_video_trends.js
COPY apps/demand-research/target_archive_client.js /app/target_archive_client.js
COPY apps/demand-research/assets /app/assets
COPY apps/demand-research/index.html /app/index.html
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 10000
CMD ["sh","-c","exec uvicorn gateway:app --host 0.0.0.0 --port ${PORT:-10000}"]
