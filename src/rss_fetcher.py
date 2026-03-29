"""
Fetches and parses RSS feeds, returning raw articles for Gemini to curate.
"""

import logging
import re
import socket
from calendar import timegm
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import feedparser

logger = logging.getLogger(__name__)

_ORIGINAL_TIMEOUT = socket.getdefaulttimeout()
_FEED_TIMEOUT = 10  # seconds per feed


@dataclass
class RawArticle:
    title: str
    url: str
    source_name: str
    published: datetime
    summary: str
    topic: str


def fetch_rss_articles(
    topic_name: str,
    feed_urls: list[str],
    cutoff_hours: int = 36,
) -> list[RawArticle]:
    """Fetch recent articles from a list of RSS feed URLs.

    Returns articles published within *cutoff_hours* of now, sorted by
    publication date (newest first). Feeds that fail are logged and skipped.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=cutoff_hours)
    articles: list[RawArticle] = []

    socket.setdefaulttimeout(_FEED_TIMEOUT)
    try:
        for url in feed_urls:
            try:
                articles.extend(_parse_feed(url, topic_name, cutoff))
            except Exception as exc:
                logger.warning(f"  Feed failed ({url}): {exc}")
    finally:
        socket.setdefaulttimeout(_ORIGINAL_TIMEOUT)

    articles.sort(key=lambda a: a.published, reverse=True)
    logger.info(
        f"  RSS: {len(articles)} articles from {len(feed_urls)} feeds "
        f"for {topic_name}"
    )
    return articles


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def _clean_source_name(title: str) -> str:
    """Strip junk from RSS feed titles to get a clean source name.

    Handles patterns like:
      "AI (artificial intelligence) | The Guardian" → "The Guardian"
      "Teesside Live | All About Boro" → "Teesside Live"  (shorter part wins)
      "News — South China Morning Post" → "South China Morning Post"
      "News - Reuters" → "Reuters"
    """
    if " | " in title:
        parts = title.split(" | ", 1)
        a, b = parts[0].strip(), parts[1].strip()
        return a if len(a) <= len(b) else b
    if " \u2014 " in title:  # em dash
        return title.split(" \u2014 ", 1)[1].strip()
    if " - " in title:
        return title.split(" - ", 1)[1].strip()
    return title.strip()


def _parse_feed(
    url: str,
    topic_name: str,
    cutoff: datetime,
) -> list[RawArticle]:
    """Parse a single RSS/Atom feed and return articles newer than cutoff."""
    feed = feedparser.parse(url)

    if feed.bozo and not feed.entries:
        raise ValueError(f"unparseable feed: {feed.bozo_exception}")

    raw_title = getattr(feed.feed, "title", None) or _domain_from_url(url)
    feed_title = _clean_source_name(raw_title)
    results: list[RawArticle] = []

    for entry in feed.entries:
        pub = _parse_date(entry)
        if pub is None or pub < cutoff:
            continue

        title = (entry.get("title") or "").strip()
        link = (entry.get("link") or "").strip()
        if not title or not link:
            continue

        summary = _extract_summary(entry)

        results.append(
            RawArticle(
                title=title,
                url=link,
                source_name=feed_title,
                published=pub,
                summary=summary[:500],
                topic=topic_name,
            )
        )

    return results


def _parse_date(entry) -> Optional[datetime]:
    """Extract a timezone-aware datetime from a feed entry."""
    for field in ("published_parsed", "updated_parsed"):
        struct = entry.get(field)
        if struct:
            try:
                return datetime.fromtimestamp(timegm(struct), tz=timezone.utc)
            except (ValueError, OverflowError):
                continue
    return None


def _extract_summary(entry) -> str:
    """Get a plain-text summary from a feed entry, stripping HTML."""
    raw = ""
    # Prefer content field (often has the full article excerpt)
    content = entry.get("content")
    if content and isinstance(content, list):
        raw = content[0].get("value", "")
    if not raw:
        raw = entry.get("summary") or entry.get("description") or ""
    # Strip HTML tags and normalise whitespace
    text = _HTML_TAG_RE.sub(" ", raw)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


def _domain_from_url(url: str) -> str:
    """Extract a readable domain name from a URL for use as source_name."""
    try:
        from urllib.parse import urlparse
        host = urlparse(url).hostname or url
        # Strip www. prefix
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return url
