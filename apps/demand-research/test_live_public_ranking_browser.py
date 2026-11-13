"""Read-only acceptance of REAL deployed public INTERSECTION RANK records.

Desktop Chromium and mobile WebKit are browser simulations, not a physical
iPhone certification. Never log names, profile URLs, post text or thumbnails.
No synthetic feed injection, bypass of restricted accounts, or storage write.
"""
from __future__ import annotations

import re
from playwright.sync_api import sync_playwright

URL="https://koith.github.io/browser-app-lab/apps/demand-research/"


def exercise(engine,label,width,height):
    browser=engine.launch(headless=True)
    try:
        page=browser.new_page(viewport={"width":width,"height":height},
                              color_scheme="light")
        response=page.goto(URL+"?qa=real-ranking",wait_until="domcontentloaded",
                           timeout=90000)
        assert response and response.status==200, "deployed Pages unavailable"
        page.locator("#activityRankingRows").wait_for(timeout=20000)
        page.wait_for_function(
            """() => typeof window.INTERSECTION_publicRankingSnapshot==='function'
                && (window.INTERSECTION_publicRankingSnapshot()?.verified||[]).length>0""",
            timeout=70000)
        page.wait_for_timeout(2500)
        result=page.evaluate("""() => {
          const snapshot=window.INTERSECTION_publicRankingSnapshot();
          const records=(snapshot?.verified||[]);
          const platforms=[...new Set(records.map(p=>p.platform))].sort();
          return {total:records.length,sourceCount:platforms.length,
                  from:Number(snapshot?.fromMs),to:Number(snapshot?.toMs)};
        }""")
        assert result["total"]>=1, "no real verified public source posts"
        assert result["from"]<result["to"], "invalid real source time window"
        assert result["sourceCount"]>=1, "missing real source provenance"
        def cohort_count(value):
            raw=page.locator('[data-rank-cohort="'+value+'"]').inner_text()
            numbers=re.findall(r"[0-9]+",raw)
            assert numbers, "rank cohort count missing"
            return int(numbers[-1])
        established=cohort_count("established")
        new=cohort_count("new")
        assert established+new>=1, "real posts never reached account ranking"
        for cohort,n in (("established",established),("new",new)):
            page.locator('[data-rank-cohort="'+cohort+'"]').click()
            cards=page.locator("#activityRankingRows .activity-rank-card")
            assert cards.count()==min(20,n), "real ranked card count incorrect"
            if n==0:
                continue
            actual=page.evaluate("""() => {
              const row=document.querySelector('#activityRankingRows');
              const item=row?.querySelector('.activity-rank-card');
              const cols=getComputedStyle(row).gridTemplateColumns.split(' ').filter(Boolean);
              const r=row.getBoundingClientRect(),c=item.getBoundingClientRect();
              return {tracks:cols.length,rowWidth:r.width,cardWidth:c.width,
                      scroll:document.documentElement.scrollWidth,
                      viewport:window.innerWidth};
            }""")
            expected=10 if width<=720 else 20
            assert actual["tracks"]==expected, (
                "10 desktop / 5 mobile rank columns did not deploy",actual["tracks"])
            assert actual["cardWidth"]<actual["rowWidth"]/(5 if width<=720 else 10), (
                "rank card grid failed responsive fit")
            assert actual["scroll"]<=actual["viewport"]+2, (
                "real ranking page has horizontal overflow")
            cards.first.click()
            dialog=page.locator("#activityRankingDialog")
            assert dialog.evaluate("(d)=>d.open"), "rank detail did not open"
            link=page.locator("#activityRankingDialogContent a[target='_blank']")
            assert link.count()==1 and (link.first.get_attribute("href") or "").startswith(
                "https://"),"rank profile source link missing"
            page.locator("#activityRankingDialogClose").click()
            assert not dialog.evaluate("(d)=>d.open"), "rank detail did not close"
            if n>20:
                page.locator("#activityRankingMore").click()
                assert cards.count()==min(n,40), "rank more must append 20"
        print("INTERSECTION_LIVE_REAL_RANKING_PASS",
              "client="+label,"verified_posts="+str(result["total"]),
              "source_count="+str(result["sourceCount"]),
              "established_accounts="+str(established),
              "new_or_unknown_accounts="+str(new),
              "columns="+str(5 if width<=720 else 10),
              "detail=PASS","pagination=PASS",flush=True)
    finally:
        browser.close()


if __name__=="__main__":
    with sync_playwright() as playwright:
        exercise(playwright.chromium,"chromium_pc",1200,900)
        exercise(playwright.webkit,"webkit_mobile_simulated",390,844)
