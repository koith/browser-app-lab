# Gallery Collector V2 — independent real-photo pilot

The existing gallery and original files stay intact. V2 does not import the
legacy direct collector, and uses the proven existing publisher only for the
final immutable file / visual duplicate / quality-upgrade transaction.

Flow: curated edition source -> bounded SQLite work queue -> robots-aware public
HTML -> observed main/article image URL -> real image bytes -> SHA + Pillow
decode -> immutable staged file -> independently verified publisher -> main
commit + compact durable checkpoint -> deployed Chromium/WebKit QA.

Offline tests:
  python apps/gallery-archive/test_collector_v2.py

No external credentials, guessed filenames, paywalls, private endpoints,
bypass of robots, paid services, or unsolicited recurring development reports.

The checkpoint apps/gallery-archive/verification/collector-v2-{model}.json
keeps works and media URLs across runners; old JPEG data and backups are never
deleted. URL checks have a bounded cooldown; blocked hosts get a longer one.
The queue only scans explicit registered public edition pages and does not yet
handle arbitrary creator feeds, dynamic browser-rendered pages or reverse-search
adapters. Those are later adapters, not prerequisites for this pilot.

CRITICAL: staged SHA count is NOT newly published photo count; HTML fetch, CI
PASS, and downloaded bytes do not by themselves prove gallery acquisition.
Only final publisher output and deployed image opening count as success.
Full manufacturer editions require every count, resolution, watermark and
available package-size evidence; public previews cannot invent paid originals.
