# Reservation monitoring: production readiness gate

## Incident 2026-10-16
The Lotte Chiikawa watcher was advertised as one-minute monitoring, but GitHub scheduled workflows executed only five times across the relevant period. The last observed scheduled run started at 08:54 KST and ended at 08:58 KST. No subsequent scheduled run was observed by 10:15 KST. A successful test push **did not** prove that the watcher was running.

## Mandatory controls for every future limited-stock reservation
1. **Independent clock**: Do not rely on GitHub Actions `schedule` as the only trigger for time-critical monitoring. Configure a separate, persistent scheduler (or an independently hosted cron service) to dispatch `workflow_dispatch` every minute. The external scheduler must be actually configured and observed; adding documentation or a workflow is not sufficient.
2. **Independent watchdog**: The scheduler or a second independent service must alert the user if no successful scan heartbeat has been recorded within 3 minutes. An in-job failure alert cannot detect a job that never starts.
3. **Live target validation**: Test real production product URLs and their actual live listing/buy states. A successful HTTP response, or zero matching cards, is not proof that the target is absent.
4. **Source freshness**: Proxy/cache responses may be stale. Log timestamp, source, response age where available, and product links; reject known stale snapshots. Do not treat repeated identical cached pages as independent checks.
5. **End-to-end rehearsal**: Before saying READY, observe >10 consecutive independently triggered scans at the requested interval, then run a controlled positive fixture through the same alert path to the user's phone.
6. **Fail loudly**: If scheduler or target verification is unproven, label the monitor NOT READY and tell the user to manually check the store. Never imply purchase availability from a listing alone.
7. **Reusable config**: Store-specific URLs, title matchers, expected products, alert topic, and monitoring dates should be parameters, not silently copied into another monitor.

## Operational status
**NOT READY FOR UNATTENDED TIME-CRITICAL USE.** GitHub Actions cron remains best-effort and is not a one-minute SLA. External scheduler and independent watchdog are not yet provisioned. Do not claim this incident is fixed until both are configured and live-tested.

## Existing manual dispatch endpoint
GitHub REST: `POST /repos/koith/browser-app-lab/actions/workflows/chiikawa-lotte-watch.yml/dispatches` with `{"ref":"main"}`, authenticated with a narrowly scoped credential. Never place tokens or Naver login sessions in the repository. Verify dispatch permissions, rate limits and actual runs before depending on this.
