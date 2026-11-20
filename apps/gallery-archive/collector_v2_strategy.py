"""V2 acquisition strategy: proof-scoped discovery, publisher gaps, identity and source variants.

A search hit is never a download authorization. Every discovered page requires
a provenance observation AND a fresh exact-edition identity check on the HTML.
Only actual embedded HTTPS image URLs enter the collector. No guessed URLs.
"""
from __future__ import annotations

from collections import defaultdict
from html import unescape
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import urljoin, urlsplit
from bs4 import BeautifulSoup


GENERIC = {
    "mimmi", "yui", "djawa", "photo", "photos", "album", "public",
    "samples", "sample", "preview", "gallery", "official", "cosplay",
    "the", "and", "of", "a", "vol", "volume", "part", "model",
    "공개", "미리보기", "사진", "화보", "심유이", "밈미", "제작",
}
MODEL_WORDS = {
    "mimmi": ("mimmi", "밈미", "mimmimimmi", "mimmissu17"),
    "yui": ("yui", "심유이", "심혜성", "super_yuisan", "sim yui", "ゆい"),
}


def normalize(text):
    return " ".join(re.findall(r"[\w]+",
        unicodedata.normalize("NFKC", str(text)).casefold()))


def edition_tokens(work):
    """Use edition-specific name/number, not merely the model identity."""
    aid = work["id"]
    from source_alias_search import IDENTITIES
    explicit = IDENTITIES.get(work.get("model", "") + ":" + aid)
    if explicit:
        return list(explicit)
    title = re.split(r"\bpublic\s+samples\b|공개\s*사진|미리보기", work["title"], 1, flags=re.I)[0]
    tokens = [x for x in normalize(title).split() if x not in GENERIC and len(x) >= 2]
    # Skip trivial title-only model pages; require a distinctive edition marker.
    return list(dict.fromkeys(tokens))[:6]


def verify_identity(raw, work, model, *, discovered=False):
    """Fresh page must contain distinctive edition tokens AND matching model.

    The model check uses article/main text; the Mimmi link in DJAWA's global
    navigation must not authorize another model's photo book.
    """
    soup = BeautifulSoup(raw[:3_000_000], "html.parser")
    heading_parts = []
    if soup.title:
        heading_parts.append(soup.title.get_text(" ", strip=True))
    heading_parts.extend(n.get_text(" ", strip=True) for n in soup.select("h1,h2")[:5])
    heading_parts.extend(str(n.get("content") or "") for n in soup.select(
        'meta[property="og:title"],meta[name="twitter:title"]')[:4])
    title = normalize(" ".join(heading_parts))
    for tag in soup.select("nav,footer,aside,header,.related,.sidebar"):
        tag.decompose()
    article = soup.select_one("article, main, .portfolio-content, .entry-content, #powerbbsContent")
    if article is None:
        return False, "missing_article"
    context = normalize(article.get_text(" ", strip=True)[:12000])
    tokens = edition_tokens({**work, "model": model})
    if not tokens:
        return False, "edition_marker_missing"
    # Unlike substring matching, a neighboring '677' must not match '1677'.
    title_words = set(title.split())
    if not all(normalize(t) in title_words or
               re.search(r"(?<!\w)" + re.escape(normalize(t)) + r"(?!\w)", title)
               for t in tokens):
        return False, "different_edition"
    if not any(re.search(r"(?<!\w)" + re.escape(normalize(m)) + r"(?!\w)", context)
               for m in MODEL_WORDS[model]):
        # Cup2D keeps its exact *model + edition* in the article H1, while
        # the remaining <article> text contains only media and comments.
        # Require actual H1/OG article title evidence; the page <title>
        # alone (which could be boilerplate) never proves a person's ID.
        exact_headings = normalize(" ".join(
            [n.get_text(" ", strip=True) for n in soup.select("article h1, main h1, h1")]
            + [str(n.get("content") or "") for n in soup.select(
                'meta[property="og:title"]')]))
        in_exact_heading = any(
            re.search(r"(?<!\w)" + re.escape(normalize(m)) + r"(?!\w)", exact_headings)
            for m in MODEL_WORDS[model])
        descriptions = normalize(" ".join(str(x.get("content") or "")
            for x in soup.select('meta[name="description"],meta[property="og:description"]')))
        in_description = any(
            re.search(r"(?<!\w)" + re.escape(normalize(m)) + r"(?!\w)", descriptions)
            for m in MODEL_WORDS[model])
        if not (in_exact_heading or in_description):
            return False, "model_not_proven_in_article"
    if "captcha" in context[:1000] or "verify you are human" in context[:1000]:
        return False, "access_challenge"
    return True, "exact_model_and_edition"


def publisher_targets(root, model):
    target = Path(root) / "apps/gallery-archive/publisher-targets.json"
    if not target.is_file():
        return {}
    doc = json.loads(target.read_text(encoding="utf-8"))
    if doc.get("schema_version") != 1:
        raise ValueError("invalid publisher target schema")
    return {row["album_id"]: row for row in doc.get("works", [])
            if row.get("model") == model and
            type(row.get("declared_photo_count")) is int and
            row["declared_photo_count"] > 0}


def source_evidence_pages(document, model, *, safe_url):
    """Reuse the project's independently approved search/reverse bridge."""
    if not document:
        return {}
    from verified_source_bridge import eligible_source_pages
    admitted = eligible_source_pages(document, model,
        lambda url, checked_model: checked_model == model and safe_url(url)
        and not urlsplit(url).path.lower().endswith((".zip",".rar",".7z",".pdf")))
    return {aid: sorted(urls)[:8] for aid, urls in admitted.items()}


def best_observed_variants(candidates, cap=200):
    """WordPress publishes multiple resized srcset URLs per SAME frame.

    Group only exact observed URLs by same-host filename stem and select
    its full-size URL when actually present, else largest observed size.
    Never generate guessed full-size filenames or mix different origins.
    """
    grouped = {}
    order = []
    for url in candidates:
        if not isinstance(url, str):
            continue
        parsed = urlsplit(url)
        name = parsed.path.rsplit("/", 1)[-1]
        resize = re.search(r"-(\d{2,5})x(\d{2,5})(?=\.(?:jpe?g|png|webp)$)", name, re.I)
        # Blogger exposes the *same* frame in an observed /s320/ tile and
        # an observed /s8640/ full-photo <a href>. Do not waste requests on
        # tiny previews or invent a higher-resolution URL.
        blogger_size = re.search(r"/s(\d{2,5})(?=/)", parsed.path, re.I) if (
            parsed.hostname or "").endswith("googleusercontent.com") else None
        if blogger_size:
            canonical_path = parsed.path.replace(
                blogger_size.group(0), "/sSIZE", 1)
            canonical = (parsed.hostname, canonical_path)
            score = (2, int(blogger_size[1]))
        else:
            canonical = (parsed.hostname, re.sub(
                r"-(\d{2,5})x(\d{2,5})(?=\.(?:jpe?g|png|webp)$)", "",
                parsed.path, flags=re.I))
            score = (1, 0) if not resize else (0, int(resize[1])*int(resize[2]))
        if canonical not in grouped:
            order.append(canonical)
            grouped[canonical] = (score, url)
        elif score > grouped[canonical][0]:
            grouped[canonical] = (score, url)
    return [grouped[k][1] for k in order[:cap]]
