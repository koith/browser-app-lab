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

## Four operational collection upgrades (2026-11-19)

1. Existing model/edition aliases and public source-name search now run before
   each bounded V2 collection. Only independently observed, exact named-work
   page proofs enter discovery. Every source page is rechecked on acquisition;
   no search-result snippet or unreviewed archive qualifies as photo proof.
2. The manufacturer's count in publisher-targets.json supersedes public
   preview-page labels. Unique SHA counts can overstate unique photographed
   frames; the reported remaining work is a conservative minimum by SHA, never
   an unverified claim of full-edition completion.
3. A bounded 12-work / 48-staged-image pilot uses at most SIX new files per
   edition in one run. One work cannot starve all others. Candidate URL
   checkpoints skip a URL only if its SHA actually appears in inventory;
   otherwise an uncommitted candidate is retried when eligible.
4. Fresh article title and contextual model/edition identity are mandatory,
   including for sites found by aliases/reverse-source evidence. Observed
   WordPress full-size URLs are preferred over observed resized variants
   without guessing any new URL paths.

References applied: Scrapy JOBDIR persistence, gallery-dl archive dedup,
WordPress responsive srcset, project's verified_source_bridge.py,
source_alias_search.py and publisher-targets.json. The old collector remains
available until this pilot passes actual acquisition and live gallery QA.
