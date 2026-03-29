"""
Deduplication for raw RSS articles and curated stories.

Two-stage dedup:
1. Exact URL match (normalised)
2. Fuzzy title match (difflib.SequenceMatcher, 0.75 threshold)
"""

import logging
import re
from difflib import SequenceMatcher
from typing import Optional
from urllib.parse import parse_qs, urlparse, urlunparse, urlencode

logger = logging.getLogger(__name__)

_FUZZY_THRESHOLD = 0.75
_PUNCT_RE = re.compile(r"[^\w\s]")


def dedup_raw_articles(articles: list) -> list:
    """Deduplicate RawArticle objects by URL and fuzzy title match.

    Keeps the article with the longer summary when a duplicate is found.
    """
    seen_urls: dict[str, int] = {}  # normalised URL → index in result
    result: list = []
    titles: list[str] = []  # parallel to result, for fuzzy matching

    for article in articles:
        norm_url = _normalise_url(article.url)

        # Stage 1: exact URL match
        if norm_url in seen_urls:
            idx = seen_urls[norm_url]
            if len(article.summary) > len(result[idx].summary):
                result[idx] = article
                titles[idx] = _normalise_title(article.title)
            continue

        # Stage 2: fuzzy title match
        norm_title = _normalise_title(article.title)
        dup_idx = _find_fuzzy_match(norm_title, titles)
        if dup_idx is not None:
            if len(article.summary) > len(result[dup_idx].summary):
                result[dup_idx] = article
                titles[dup_idx] = norm_title
                seen_urls[norm_url] = dup_idx
            continue

        # No duplicate — add it
        seen_urls[norm_url] = len(result)
        result.append(article)
        titles.append(norm_title)

    if len(articles) != len(result):
        logger.info(
            f"  Dedup: {len(articles)} → {len(result)} articles "
            f"({len(articles) - len(result)} duplicates removed)"
        )
    return result


def dedup_stories(stories: list) -> list:
    """Deduplicate Story objects across topics by URL and fuzzy headline match."""
    seen_urls: set[str] = set()
    result: list = []
    titles: list[str] = []

    for story in stories:
        norm_url = _normalise_url(story.source_url) if story.source_url else ""

        if norm_url and norm_url in seen_urls:
            continue

        norm_title = _normalise_title(story.headline)
        if _find_fuzzy_match(norm_title, titles) is not None:
            continue

        if norm_url:
            seen_urls.add(norm_url)
        result.append(story)
        titles.append(norm_title)

    if len(stories) != len(result):
        logger.info(
            f"  Cross-topic dedup: {len(stories)} → {len(result)} stories"
        )
    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _normalise_url(url: str) -> str:
    """Normalise a URL for dedup: lowercase domain, strip trailing slash,
    remove utm_* and tracking params."""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        # Lowercase the domain
        netloc = (parsed.netloc or "").lower()
        # Strip trailing slash from path
        path = parsed.path.rstrip("/")
        # Remove tracking params
        params = parse_qs(parsed.query, keep_blank_values=False)
        clean_params = {
            k: v for k, v in params.items()
            if not k.startswith("utm_") and k not in ("ref", "source", "fbclid")
        }
        query = urlencode(clean_params, doseq=True) if clean_params else ""
        return urlunparse((parsed.scheme, netloc, path, "", query, ""))
    except Exception:
        return url.lower().rstrip("/")


def _normalise_title(title: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    text = _PUNCT_RE.sub(" ", title.lower())
    return " ".join(text.split())


def _find_fuzzy_match(title: str, existing: list[str]) -> Optional[int]:
    """Return index of the first fuzzy match in existing titles, or None."""
    if not title:
        return None
    for i, existing_title in enumerate(existing):
        if SequenceMatcher(None, title, existing_title).ratio() >= _FUZZY_THRESHOLD:
            return i
    return None
