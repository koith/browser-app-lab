#!/usr/bin/env python3
"""Read-only Pages browser check of deployed gallery quality-preference code.

Real committed gallery metadata supplies the two distinct existing SHA IDs.
Paired optical evidence is deliberately synthetic: this verifies selector
behavior, NOT visual identity or the actual optical quality of those photos.
"""
from __future__ import annotations

import argparse
import json
from playwright.sync_api import sync_playwright

ROOT = "https://koith.github.io/browser-app-lab/apps"


def check(browser, model: str) -> None:
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, is_mobile=True,
        has_touch=True, device_scale_factor=2, locale="ko-KR",
    )
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)[:180]))
    try:
        response = page.goto(f"{ROOT}/{model}-gallery/",
                             wait_until="domcontentloaded", timeout=60000)
        assert response and response.status == 200, (model, "Pages HTML")
        page.wait_for_function("""() => typeof GalleryPhotoQuality?.preferred === 'function' &&
          typeof stored !== 'undefined' && Array.isArray(stored) &&
          stored.some(a => photosFor(a).some(p => p.ownerAlbum))
        """, timeout=70000)
        result = page.evaluate("""() => {
          const all=stored.flatMap(a=>photosFor(a));
          const sha=p=>typeof p?.sha256==='string' && /^[0-9a-f]{64}$/.test(p.sha256);
          const first=all.find(p=>p.ownerAlbum && sha(p));
          const second=all.find(p=>sha(p) && p.sha256!==first?.sha256);
          if(!first||!second)throw Error('no two distinct real stored SHAs');
          const q=GalleryPhotoQuality;
          const original={...first,watermark_status:'present_verified',
            visual_quality:{method:'decoded-pixel-v1',photo_sha256:first.sha256,
              confidence:'measured',score:40}};
          const unrelated={...second,ownerAlbum:undefined,vaultAlbum:undefined,
            watermark_status:'absent_verified',
            visual_quality:{method:'decoded-pixel-v1',photo_sha256:second.sha256,
              confidence:'measured',score:98}};
          const falsePair={...unrelated,visual_quality:{
            ...unrelated.visual_quality,same_photo_verified:true,
            compared_to_sha256:'f'.repeat(64)}};
          const provenHigher={...unrelated,visual_quality:{
            method:'paired-decoded-pixel-v1',candidate_sha256:second.sha256,
            compared_to_sha256:first.sha256,same_photo_verified:true,
            confidence:'measured',relation:'higher'}};
          const provenComparable={...provenHigher,visual_quality:{
            ...provenHigher.visual_quality,relation:'comparable'}};
          const staleScore={...unrelated,visual_quality:{
            ...unrelated.visual_quality,photo_sha256:first.sha256}};
          const assertions={
            preserve_owner_over_unknown_unrelated_score:q.preferred(original,unrelated)===original,
            reject_wrong_pair_sha:q.preferred(original,falsePair)===original,
            verified_pair_can_promote:q.preferred(original,provenHigher)===provenHigher,
            comparable_verified_clean_wins:q.preferred(original,provenComparable)===provenComparable,
            reject_score_reused_across_sha:q.score(staleScore)===null,
            byte_identical_archive_preserved:q.preferred(original,{
              ...unrelated,sha256:first.sha256})===original
          };
          return {model:'MODEL',scanned_viewer_rows:all.length,
            has_two_distinct_owner_sha:true,
            assertions,synthetic_paired_evidence_only:true,
            private_original_pixel_bytes_compared:false};
        }""".replace("MODEL", model))
        failed = [k for k, ok in result["assertions"].items() if not ok]
        assert not failed, (model, "deployed selector regression", failed, result)
        assert not errors, (model, "browser JavaScript errors", errors)
        print("GALLERY_LIVE_QUALITY_SELECTOR_GUARD_PASS",
              json.dumps(result, ensure_ascii=False), flush=True)
    finally:
        context.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser", choices=("chromium", "webkit"), required=True)
    args = parser.parse_args()
    with sync_playwright() as playwright:
        browser = getattr(playwright, args.browser).launch(headless=True)
        try:
            for model in ("mimmi", "yui"):
                check(browser, model)
        finally:
            browser.close()
    print("BOTH_MODELS_DEPLOYED_QUALITY_SELECTOR_PASS", args.browser, flush=True)


if __name__ == "__main__":
    main()
