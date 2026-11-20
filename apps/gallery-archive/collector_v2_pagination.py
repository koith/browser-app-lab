"""Read only publicly rendered, observed numbered gallery pages.

The caller has already fetched and checked the registered public source with
its robots policy. Browser navigation never guesses URLs, uses credentials,
or reads protected downloads. Media bytes are separately authorized, decoded,
de-duplicated and committed by the existing V2 collector/publisher.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit
from bs4 import BeautifulSoup


def observed_numeric_page_buttons(raw):
    """Only actual visible numeric pagination controls; not fabricated pages."""
    soup = BeautifulSoup(raw, "html.parser")
    found = set()
    for el in soup.select("button"):
        label = el.get_text(" ", strip=True)
        if (re.fullmatch(r"[1-9][0-9]{0,2}", label)
                and not el.has_attr("disabled")
                and el.get("aria-hidden") != "true"):
            found.add(int(label))
    return sorted(found)


def discover_rendered_button_pages(url, verify_page, extract_images, max_pages=5):
    """Return (observed public image URLs, inspected page count).

    Clicking is restricted to the already-visible numeric buttons on the
    registered gallery. Every updated DOM must still prove the SAME edition.
    """
    if not 1 <= max_pages <= 20:
        raise ValueError("invalid_rendered_page_budget")
    from playwright.sync_api import sync_playwright

    host = urlsplit(url).hostname
    candidates = []
    seen = set()
    inspected = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(
                viewport={"width": 1280, "height": 900}, service_workers="block")
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=35000)
            page.wait_for_timeout(550)

            def inspect():
                nonlocal inspected
                if urlsplit(page.url).hostname != host:
                    return False
                # Scroll normal public content to activate visible lazy images.
                page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
                page.wait_for_timeout(300)
                html = page.content().encode("utf-8")
                if not verify_page(html):
                    return False
                inspected += 1
                for photo in extract_images(html, page.url):
                    if photo not in seen:
                        seen.add(photo)
                        candidates.append(photo)
                return True

            if not inspect():
                return [], inspected
            original_html = page.content().encode("utf-8")
            numbers = [n for n in observed_numeric_page_buttons(original_html)
                       if n != 1][:max_pages-1]
            for n in numbers:
                button = page.get_by_role("button", name=str(n), exact=True)
                if button.count() != 1:
                    continue
                button.click(timeout=9000)
                page.wait_for_timeout(500)
                if not inspect():
                    break
        finally:
            browser.close()
    return candidates, inspected
