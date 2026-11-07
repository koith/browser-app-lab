"""Read-only real-browser probe of the already-created public Worker; no secrets."""
import argparse
import asyncio
import json
import hashlib
from pathlib import Path
from playwright.async_api import async_playwright

BASE = "https://gallery-archive-free.gallery-9f7d03138f3f.workers.dev"
URL = BASE + "/api/v1/health"
ROOT = Path(__file__).resolve().parents[2]


def sample(model):
    # Select an owner-index photo that is already byte-identical to a
    # committed first-party stored original, not a third-party preview URL.
    home = ROOT / "apps" / (model + "-gallery")
    owner = json.loads((home / "owner-index.json").read_text())
    stored = json.loads((home / "stored-albums.json").read_text())
    signatures = {}
    for album in stored["albums"]:
        for photo in album["images"]:
            sig = tuple(photo.get(k) for k in ("sha256", "bytes", "width", "height"))
            path = photo.get("url", "")
            if (isinstance(path, str) and path.startswith("stored-albums/") and
                    ".." not in path.split("/")):
                signatures[sig] = path
    for album in owner["albums"]:
        for photo in album["images"]:
            sig = tuple(photo.get(k) for k in ("sha256", "bytes", "width", "height"))
            relative = signatures.get(sig)
            if not relative:
                continue
            raw = (home / relative).read_bytes()
            if len(raw) != photo["bytes"] or hashlib.sha256(raw).hexdigest() != photo["sha256"]:
                continue
            return {"model": model, "album": album["id"], "number": photo["number"],
                    "sha256": photo["sha256"], "bytes": photo["bytes"],
                    "width": photo["width"], "height": photo["height"]}
    raise AssertionError("NO_EXACT_PAGES_OWNER_PHOTO_FOR_" + model)


async def verify(engine):
    async with async_playwright() as pw:
        browser = await getattr(pw, engine).launch(headless=True)
        try:
            page = await browser.new_page(viewport={"width": 390, "height": 844})
            response = await page.goto(URL, wait_until="domcontentloaded", timeout=30000)
            status = response.status if response else 0
            ctype = response.headers.get("content-type", "") if response else ""
            if status != 200:
                print("GALLERY_REAL_WORKER_BROWSER_HEALTH", engine,
                      "http", status, "content_type",
                      "JSON" if "json" in ctype else "HTML" if "html" in ctype else "OTHER",
                      flush=True)
                raise AssertionError("REAL_WORKER_NOT_HEALTHY_IN_" + engine.upper())
            body = await response.json()
            if (not isinstance(body, dict) or
                body.get("transport") != "cloudflare-bound-assets" or
                not isinstance(body.get("source_commit"), str) or
                len(body["source_commit"]) != 40):
                raise AssertionError("WORKER_HEALTH_SCHEMA_MISMATCH")
            print("GALLERY_REAL_WORKER_BROWSER_HEALTH", engine,
                  "http", status, "expected_transport", True, flush=True)
            for model in ("mimmi", "yui"):
                photo = sample(model)
                # Browser MUST originate on real GitHub Pages. This executes
                # its actual CORS preflight + SHA-bound signing + original GET.
                await page.goto("https://koith.github.io/browser-app-lab/apps/"
                                + model + "-gallery/", wait_until="domcontentloaded",
                                timeout=45000)
                result = await page.evaluate("""async ({base, photo}) => {
                  const signed=await fetch(base+'/api/v1/sign',{
                    method:'POST',credentials:'omit',cache:'no-store',
                    headers:{'Content-Type':'application/json'},
                    body:JSON.stringify({model:photo.model,album:photo.album,
                      number:photo.number,variant:'original',sha256:photo.sha256})
                  });
                  if(signed.status!==200)return {phase:'sign',http:signed.status};
                  const metadata=await signed.json();
                  if(metadata.sha256!==photo.sha256||metadata.bytes!==photo.bytes)
                    return {phase:'signed_metadata_mismatch'};
                  const url=new URL(metadata.url);
                  if(url.origin!==base||url.pathname!==
                      '/api/v1/media/'+[photo.model,photo.album,photo.number,'original'].join('/'))
                    return {phase:'signed_url_mismatch'};
                  const image=new Image();image.src=url.href;
                  try {await image.decode()}catch(e){return {phase:'decode_failed'}};
                  const response=await fetch(url.href,{credentials:'omit',cache:'no-store'});
                  if(response.status!==200)return {phase:'original_fetch',http:response.status};
                  const bytes=await response.arrayBuffer();
                  const hash=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))]
                    .map(b=>b.toString(16).padStart(2,'0')).join('');
                  return {phase:'pass',width:image.naturalWidth,height:image.naturalHeight,
                    bytes:bytes.byteLength,sha256:hash};
                }""", {"base": BASE, "photo": photo})
                if (result.get("phase") != "pass" or
                    tuple(result.get(k) for k in ("sha256", "bytes", "width", "height")) !=
                    tuple(photo[k] for k in ("sha256", "bytes", "width", "height"))):
                    print("GALLERY_REMOTE_PHOTO_BROWSER_FAIL", engine, model,
                          "phase", result.get("phase"), "http", result.get("http", "none"),
                          flush=True)
                    raise AssertionError("REAL_REMOTE_ORIGINAL_NOT_VERIFIED_" + model)
                print("GALLERY_REMOTE_PHOTO_BROWSER_PASS", engine, model,
                      "sha_bytes_pixels_verified", True, flush=True)
        finally:
            await browser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser", choices=("webkit", "chromium"), required=True)
    options = parser.parse_args()
    asyncio.run(verify(options.browser))
