"""
Curates news stories using Gemini from a pre-fetched RSS article pool.

For most topics, Gemini receives RSS articles and selects/summarises the best.
For topics with use_grounding_fallback=True, Gemini also searches Google
when RSS coverage is thin.
"""

import json
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from google import genai
from google.genai import types

from .config import (
    MODEL,
    MAX_OUTPUT_TOKENS,
    CURATION_SYSTEM_PROMPT,
    GROUNDING_SYSTEM_PROMPT,
    TOPICS,
    Topic,
)
from .rss_fetcher import RawArticle

logger = logging.getLogger(__name__)


@dataclass
class Story:
    headline: str
    summary: str
    source_name: str
    source_url: str
    importance: str  # "high", "medium", "low"
    topic: str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def curate_all_stories(
    client: genai.Client,
    today_date: date,
    articles_by_topic: dict[str, list[RawArticle]],
) -> dict[str, list[Story]]:
    """Curate stories for every configured topic.

    For each topic, sends the RSS article pool to Gemini for curation.
    For fallback topics with thin results, also runs a grounded search.
    """
    today = today_date.strftime("%A, %-d %B %Y")
    yesterday = (today_date - timedelta(days=1)).strftime("%A, %-d %B %Y")

    results: dict[str, list[Story]] = {}
    for topic in TOPICS:
        articles = articles_by_topic.get(topic.name, [])
        logger.info(f"Curating: {topic.name} ({len(articles)} RSS articles)")

        stories = _curate_topic(client, topic, today, yesterday, articles)

        # Grounding fallback for topics with thin RSS coverage
        if topic.use_grounding_fallback and len(stories) < 2:
            logger.info(
                f"  Fallback: running grounded search for {topic.name} "
                f"({len(stories)} stories from RSS)"
            )
            existing = [s.headline for s in stories]
            grounded = _fetch_grounded_topic(
                client, topic, today, yesterday, existing
            )
            stories.extend(grounded)

        results[topic.name] = stories
        logger.info(f"  Got {len(stories)} stories for {topic.name}")

    return results


def fetch_intro(
    client: genai.Client,
    stories_by_topic: dict[str, list[Story]],
    today: str,
) -> str:
    """Generate a short, conversational intro paragraph summarising the top stories.

    Uses Gemini without grounding — writes from headlines already gathered.
    Returns an empty string on failure.
    """
    all_stories = [s for stories in stories_by_topic.values() for s in stories]
    if not all_stories:
        return ""

    rank = {"high": 0, "medium": 1, "low": 2}
    all_stories.sort(key=lambda s: rank.get(s.importance, 1))
    top = all_stories[:5]

    stories_text = "\n".join(
        f"- {s.headline} (section: {s.topic})" for s in top
    )

    system = (
        "You are a newsletter writer. Write in Australian English. "
        "Your output must be ONLY the requested paragraph — no headings, "
        "no commentary, no meta-text, no bullet points."
    )

    prompt = (
        f"Today is {today}. Here are the top news stories:\n\n"
        f"{stories_text}\n\n"
        "Write a 2-3 sentence intro paragraph for a morning news email. "
        "Mention 3-4 of these stories by name. Be direct and punchy — "
        "like a colleague giving you a 10-second briefing. "
        "No greeting. No sign-off. Just the paragraph."
    )

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=2048,
                temperature=0.4,
            ),
        )
        try:
            finish = response.candidates[0].finish_reason
            logger.info(f"Intro finish_reason: {finish}")
        except (AttributeError, IndexError):
            pass

        intro_text = (response.text or "").strip()

        if intro_text:
            logger.info(f"Intro ({len(intro_text)} chars): {intro_text}")
            # If truncated (no period at end), try to salvage
            if not intro_text.endswith((".", "!", "?")):
                last_period = intro_text.rfind(".")
                if last_period > 0:
                    intro_text = intro_text[:last_period + 1]
                    logger.info(
                        f"Trimmed to last complete sentence "
                        f"({len(intro_text)} chars)"
                    )
            return intro_text
        else:
            logger.warning("Intro response was empty")
    except Exception as exc:
        logger.error(f"Error generating intro: {exc}")

    return ""


# ---------------------------------------------------------------------------
# Curation (RSS → Gemini → Stories)
# ---------------------------------------------------------------------------


def _curate_topic(
    client: genai.Client,
    topic: Topic,
    today: str,
    yesterday: str,
    articles: list[RawArticle],
) -> list[Story]:
    """Send RSS article pool to Gemini for curation and ranking."""
    if not articles:
        logger.info(f"  No RSS articles for {topic.name}, skipping curation")
        return []

    # Cap at 100 most recent articles
    pool = articles[:100]
    article_text = _format_article_pool(pool)

    # Build the valid URL set for validation
    valid_urls = {a.url for a in pool}

    system = CURATION_SYSTEM_PROMPT.format(today=today, yesterday=yesterday)
    prompt = topic.prompt.format(articles=article_text)

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=0.1,
                max_output_tokens=MAX_OUTPUT_TOKENS,
            ),
        )
    except Exception as exc:
        logger.error(f"Gemini API error curating {topic.name}: {exc}")
        return []

    stories = _parse_response(response, topic.name)

    # Validate URLs — drop stories with missing or unrecognised URLs
    validated: list[Story] = []
    for story in stories:
        if story.source_url and story.source_url in valid_urls:
            validated.append(story)
        else:
            logger.warning(
                f"  Dropped story (bad URL): {story.headline!r} "
                f"→ {story.source_url!r}"
            )
    logger.info(
        f"  Curation: {len(validated)}/{len(stories)} stories have valid URLs"
    )
    return validated


def _format_article_pool(articles: list[RawArticle]) -> str:
    """Format articles as a numbered text block for the Gemini prompt."""
    lines: list[str] = []
    for i, a in enumerate(articles, 1):
        pub_str = a.published.strftime("%d %b %Y %H:%M UTC")
        summary = a.summary[:200] if a.summary else "(no summary)"
        lines.append(
            f"[{i}] Title: {a.title}\n"
            f"    Source: {a.source_name} | URL: {a.url}\n"
            f"    Published: {pub_str}\n"
            f"    Summary: {summary}"
        )
    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# Grounding fallback (Canberra & Sports only)
# ---------------------------------------------------------------------------


def _fetch_grounded_topic(
    client: genai.Client,
    topic: Topic,
    today: str,
    yesterday: str,
    existing_headlines: list[str],
) -> list[Story]:
    """Search Google via Gemini grounding for a topic, avoiding duplicates.

    Stories without a matched grounding URL are dropped.
    """
    system = GROUNDING_SYSTEM_PROMPT.format(today=today, yesterday=yesterday)

    # Build prompt that tells Gemini what we already have
    prompt_parts = [topic.prompt.split("\n\nARTICLE POOL:")[0]]  # base prompt
    if existing_headlines:
        prompt_parts.append(
            "\n\nI already have these stories from RSS feeds:\n"
            + "\n".join(f"- {h}" for h in existing_headlines)
            + "\n\nFind additional stories NOT already covered above."
        )
    prompt = "\n".join(prompt_parts)

    # For grounded search, we need a search-style prompt
    search_prompt = (
        f"Search for the latest news about {topic.name} published today or "
        f"yesterday. {prompt}"
    )

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=search_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.1,
                max_output_tokens=MAX_OUTPUT_TOKENS,
            ),
        )
    except Exception as exc:
        logger.error(f"Gemini grounding error for {topic.name}: {exc}")
        return []

    stories = _parse_response(response, topic.name)

    # Fill URLs from grounding metadata
    _enrich_with_grounding_supports(response, stories)
    grounding_urls = _extract_grounding_urls(response)
    _enrich_with_grounding_domain(stories, grounding_urls)

    # Drop stories without URLs
    with_urls = [s for s in stories if s.source_url]
    dropped = len(stories) - len(with_urls)
    if dropped:
        logger.info(f"  Grounding: dropped {dropped} stories without URLs")
    logger.info(
        f"  Grounding: {len(with_urls)} stories with URLs for {topic.name}"
    )
    return with_urls


# ---------------------------------------------------------------------------
# Response parsing (shared by curation and grounding)
# ---------------------------------------------------------------------------


def _parse_response(response, topic_name: str) -> list[Story]:
    """Extract the JSON stories array from the Gemini response text."""
    raw = _extract_model_text(response)
    if not raw:
        logger.warning(f"Empty response for {topic_name}")
        return []

    raw = raw.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]).strip()

    data = _safe_json_loads(raw, topic_name)
    if data is None:
        return []

    stories: list[Story] = []
    for item in data.get("stories", []):
        stories.append(
            Story(
                headline=item.get("headline", "Untitled"),
                summary=item.get("summary", ""),
                source_name=item.get("source_name", ""),
                source_url=item.get("source_url", ""),
                importance=item.get("importance", "medium"),
                topic=topic_name,
            )
        )
    return stories


def _extract_model_text(response) -> str:
    """Extract only the model-generated text from a Gemini response.

    Gemini with grounding returns multiple parts — some are search snippets.
    We want only the text parts that contain our JSON.
    """
    try:
        parts = response.candidates[0].content.parts
        texts = []
        for part in parts:
            if hasattr(part, "text") and part.text:
                texts.append(part.text)
        if texts:
            for text in texts:
                if '"stories"' in text:
                    return text
            return "\n".join(texts)
    except (AttributeError, IndexError):
        pass
    return getattr(response, "text", None) or ""


def _safe_json_loads(raw: str, topic_name: str) -> Optional[dict]:
    """Try to parse JSON, with fallbacks for extraction and truncation repair."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(raw[start:end])
        except json.JSONDecodeError:
            pass

    if start >= 0:
        repaired = _repair_truncated_json(raw[start:])
        if repaired is not None:
            logger.info(f"Recovered truncated JSON for {topic_name}")
            return repaired

    logger.error(f"Failed to parse JSON for {topic_name}: {raw[:500]}")
    return None


def _repair_truncated_json(raw: str) -> Optional[dict]:
    """Attempt to repair truncated JSON by closing open structures."""
    last_complete = raw.rfind("}")
    if last_complete < 0:
        return None

    pos = last_complete
    while pos > 0:
        attempt = raw[:pos + 1] + "]}"
        try:
            return json.loads(attempt)
        except json.JSONDecodeError:
            pass
        pos = raw.rfind("}", 0, pos)

    return None


# ---------------------------------------------------------------------------
# Grounding URL enrichment (for fallback topics only)
# ---------------------------------------------------------------------------


def _extract_grounding_urls(response) -> dict[str, str]:
    """Extract source URLs from Gemini grounding metadata."""
    urls: dict[str, str] = {}
    try:
        metadata = response.candidates[0].grounding_metadata
        if metadata is None:
            logger.info("  No grounding_metadata on response")
            return urls

        chunks = getattr(metadata, "grounding_chunks", None) or []
        for chunk in chunks:
            if hasattr(chunk, "web") and chunk.web and chunk.web.uri:
                title = chunk.web.title or ""
                urls[title] = chunk.web.uri

        supports = getattr(metadata, "grounding_supports", None) or []
        for support in supports:
            indices = getattr(support, "grounding_chunk_indices", []) or []
            for ref in indices:
                if ref < len(chunks):
                    chunk = chunks[ref]
                    if hasattr(chunk, "web") and chunk.web and chunk.web.uri:
                        title = chunk.web.title or ""
                        urls[title] = chunk.web.uri

        if not urls:
            logger.info(
                f"  No URLs found. chunks={len(chunks)}, "
                f"supports={len(supports)}"
            )
    except (AttributeError, IndexError) as exc:
        logger.warning(f"  Error extracting grounding URLs: {exc}")
    return urls


def _enrich_with_grounding_supports(
    response, stories: list[Story]
) -> None:
    """Map stories to URLs using grounding_supports segment data."""
    try:
        metadata = response.candidates[0].grounding_metadata
        if not metadata:
            return

        chunks = getattr(metadata, "grounding_chunks", None) or []
        supports = getattr(metadata, "grounding_supports", None) or []

        if not chunks or not supports:
            return

        segment_urls: list[tuple[str, str]] = []
        for support in supports:
            segment = getattr(support, "segment", None)
            seg_text = getattr(segment, "text", "") if segment else ""
            indices = getattr(support, "grounding_chunk_indices", []) or []

            for idx in indices:
                if idx < len(chunks):
                    chunk = chunks[idx]
                    if hasattr(chunk, "web") and chunk.web and chunk.web.uri:
                        segment_urls.append((seg_text.lower(), chunk.web.uri))

        if not segment_urls:
            return

        stop_words = {
            "the", "a", "an", "in", "on", "at", "to", "for", "of", "and",
            "is", "are", "was", "has", "as", "by", "with", "from", "new",
            "its", "it", "be", "but", "or", "not", "up", "out", "over",
        }
        matched = 0
        for story in stories:
            if story.source_url:
                continue

            text_lower = f"{story.headline} {story.summary}".lower()
            content_words = set(text_lower.split()) - stop_words

            best_url = ""
            best_overlap = 0
            for seg_text, url in segment_urls:
                seg_words = set(seg_text.split())
                overlap = len(content_words & seg_words)
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_url = url

            if best_url and best_overlap >= 2:
                story.source_url = best_url
                matched += 1

        if matched:
            logger.info(f"  Supports matched {matched} stories with URLs")

    except (AttributeError, IndexError) as exc:
        logger.debug(f"  Error in grounding_supports: {exc}")


def _enrich_with_grounding_domain(
    stories: list[Story], grounding_urls: dict[str, str]
) -> None:
    """Fallback: match stories to grounding URLs by source name → domain."""
    if not grounding_urls:
        return

    url_list = list(grounding_urls.items())
    matched = 0

    aliases = {
        "abc": "abc.net", "abc news": "abc.net",
        "sbs": "sbs.com", "sbs news": "sbs.com",
        "guardian": "theguardian", "the guardian": "theguardian",
        "bbc": "bbc.co", "bbc news": "bbc.co",
        "reuters": "reuters.com",
        "ap": "apnews", "associated press": "apnews",
        "smh": "smh.com", "sydney morning herald": "smh.com",
        "the age": "theage.com",
        "afr": "afr.com", "financial review": "afr.com",
        "canberra times": "canberratimes", "riotact": "riotact",
        "nine": "9news", "nine news": "9news",
        "seven": "7news", "seven news": "7news",
        "fox sports": "foxsports", "espn": "espn",
        "nrl": "nrl.com", "cricket australia": "cricket.com.au",
        "nca newswire": "news.com",
    }

    for story in stories:
        if story.source_url:
            continue

        source = story.source_name.lower().strip()
        alias_match = aliases.get(source, "")
        source_norm = (
            source.replace("the ", "")
            .replace(" news", "")
            .replace(" australia", "")
            .replace(" ", "")
            .strip()
        )

        for title, url in url_list:
            title_lower = title.lower()
            domain = (
                title_lower.replace(".com", "")
                .replace(".au", "")
                .replace(".co.uk", "")
                .replace(".org", "")
                .replace(".net", "")
            )

            if alias_match and alias_match in title_lower:
                story.source_url = url
                matched += 1
                break
            elif source_norm and (
                source_norm in domain or domain in source_norm
            ):
                story.source_url = url
                matched += 1
                break

    total_with_urls = sum(1 for s in stories if s.source_url)
    logger.info(f"  URLs: {total_with_urls}/{len(stories)} stories have links")
