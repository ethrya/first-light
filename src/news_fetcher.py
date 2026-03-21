"""
Fetches news for each topic using the Gemini API with Google Search grounding.
Returns structured story data with source links.
"""

import json
import logging
from dataclasses import dataclass
from datetime import date, timedelta

from google import genai
from google.genai import types

from .config import MODEL, MAX_OUTPUT_TOKENS, SYSTEM_PROMPT, TOPICS, Topic

logger = logging.getLogger(__name__)


@dataclass
class Story:
    headline: str
    summary: str
    source_name: str
    source_url: str
    importance: str  # "high", "medium", "low"
    topic: str


def fetch_all_stories(
    client: genai.Client,
    today_date: date,
) -> dict[str, list[Story]]:
    """Fetch stories for every configured topic.

    Returns a dict mapping topic names to story lists.
    """
    today = today_date.strftime("%A, %-d %B %Y")
    yesterday = (today_date - timedelta(days=1)).strftime("%A, %-d %B %Y")

    results: dict[str, list[Story]] = {}
    for topic in TOPICS:
        logger.info(f"Fetching stories for: {topic.name}")
        stories = _fetch_topic(client, topic, today, yesterday)
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
        # Log finish reason to diagnose truncation
        try:
            finish = response.candidates[0].finish_reason
            logger.info(f"Intro finish_reason: {finish}")
        except (AttributeError, IndexError):
            pass

        intro_text = (response.text or "").strip()

        if intro_text:
            logger.info(f"Intro ({len(intro_text)} chars): {intro_text}")
            # If truncated (no period at end), try to salvage
            if intro_text and not intro_text.endswith((".", "!", "?")):
                last_period = intro_text.rfind(".")
                if last_period > 0:
                    intro_text = intro_text[:last_period + 1]
                    logger.info(f"Trimmed to last complete sentence ({len(intro_text)} chars)")
            return intro_text
        else:
            logger.warning("Intro response was empty")
    except Exception as exc:
        logger.error(f"Error generating intro: {exc}")

    return ""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _fetch_topic(
    client: genai.Client,
    topic: Topic,
    today: str,
    yesterday: str,
) -> list[Story]:
    """Make a single Gemini API call with Google Search grounding for one topic."""
    system = SYSTEM_PROMPT.format(today=today, yesterday=yesterday)

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=topic.prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.1,
                max_output_tokens=MAX_OUTPUT_TOKENS,
            ),
        )
    except Exception as exc:
        logger.error(f"Gemini API error fetching {topic.name}: {exc}")
        return []

    stories = _parse_response(response, topic.name)

    # Fill source URLs from grounding metadata
    _enrich_with_grounding_supports(response, stories)
    grounding_urls = _extract_grounding_urls(response)
    _enrich_with_grounding_domain(stories, grounding_urls)

    return stories


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
                source_url="",  # filled from grounding metadata only
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
            # Find the part that looks like JSON (contains "stories")
            for text in texts:
                if '"stories"' in text:
                    return text
            # Fallback: concatenate all text parts
            return "\n".join(texts)
    except (AttributeError, IndexError):
        pass

    # Final fallback: response.text
    return getattr(response, "text", None) or ""


def _safe_json_loads(raw: str, topic_name: str) -> dict | None:
    """Try to parse JSON, with fallbacks for extraction and truncation repair."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Fallback 1: find the outermost { … }
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(raw[start:end])
        except json.JSONDecodeError:
            pass

    # Fallback 2: truncated JSON — close open brackets and try again
    if start >= 0:
        repaired = _repair_truncated_json(raw[start:])
        if repaired is not None:
            logger.info(f"Recovered truncated JSON for {topic_name}")
            return repaired

    logger.error(f"Failed to parse JSON for {topic_name}: {raw[:500]}")
    return None


def _repair_truncated_json(raw: str) -> dict | None:
    """Attempt to repair truncated JSON by closing open structures.

    If the response was cut off mid-JSON (e.g. by max_output_tokens),
    we find the last complete story object and close the array/object.
    """
    # Find the last complete story object (ends with })
    # Look for "},\n    {" or just "}" followed by incomplete content
    last_complete = raw.rfind("}")
    if last_complete < 0:
        return None

    # Walk backwards to find a position where closing ]} makes valid JSON
    pos = last_complete
    while pos > 0:
        attempt = raw[:pos + 1] + "]}"
        try:
            return json.loads(attempt)
        except json.JSONDecodeError:
            pass
        # Try next } backwards
        pos = raw.rfind("}", 0, pos)

    return None


def _extract_grounding_urls(response) -> dict[str, str]:
    """Extract source URLs from Gemini grounding metadata.

    Returns a mapping of title → URL.
    """
    urls: dict[str, str] = {}
    try:
        metadata = response.candidates[0].grounding_metadata
        if metadata is None:
            logger.info("  No grounding_metadata on response")
            return urls

        # Try grounding_chunks
        chunks = getattr(metadata, "grounding_chunks", None) or []
        for chunk in chunks:
            if hasattr(chunk, "web") and chunk.web and chunk.web.uri:
                title = chunk.web.title or ""
                urls[title] = chunk.web.uri
                logger.info(f"  Chunk: {title!r} → {chunk.web.uri[:80]}")

        # Also try grounding_supports which reference chunks by index
        supports = getattr(metadata, "grounding_supports", None) or []
        for support in supports:
            indices = getattr(support, "grounding_chunk_indices", []) or []
            for ref in indices:
                if ref < len(chunks):
                    chunk = chunks[ref]
                    if hasattr(chunk, "web") and chunk.web and chunk.web.uri:
                        title = chunk.web.title or ""
                        urls[title] = chunk.web.uri

        # Log retrieval queries if available
        queries = getattr(metadata, "web_search_queries", None)
        if queries:
            logger.info(f"  Search queries used: {queries[:3]}")

        if not urls:
            logger.info(f"  No URLs found. chunks={len(chunks)}, supports={len(supports)}")

    except (AttributeError, IndexError) as exc:
        logger.warning(f"  Error extracting grounding URLs: {exc}")
    return urls


def _enrich_with_grounding_supports(response, stories: list[Story]) -> None:
    """Map stories to URLs using grounding_supports segment data.

    grounding_supports maps segments of response text to specific grounding
    chunk indices. We match story headlines/summaries to these segments to
    find the correct URL for each story.
    """
    try:
        metadata = response.candidates[0].grounding_metadata
        if not metadata:
            return

        chunks = getattr(metadata, "grounding_chunks", None) or []
        supports = getattr(metadata, "grounding_supports", None) or []

        if not chunks or not supports:
            return

        # Build list of (segment_text, url) from supports
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

        matched = 0
        stop_words = {
            "the", "a", "an", "in", "on", "at", "to", "for", "of", "and",
            "is", "are", "was", "has", "as", "by", "with", "from", "new",
            "its", "it", "be", "but", "or", "not", "up", "out", "over",
        }

        for story in stories:
            if story.source_url:  # already has a URL
                continue

            # Use both headline and summary words for matching
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


def _enrich_with_grounding_domain(stories: list[Story], grounding_urls: dict[str, str]) -> None:
    """Fallback: match stories to grounding URLs by source name → domain.

    Only applies to stories that don't already have a URL from supports matching.
    """
    if not grounding_urls:
        return

    url_list = list(grounding_urls.items())
    matched = 0

    # Common aliases: source_name → domain fragment
    aliases = {
        "abc": "abc.net",
        "abc news": "abc.net",
        "sbs": "sbs.com",
        "sbs news": "sbs.com",
        "guardian": "theguardian",
        "the guardian": "theguardian",
        "bbc": "bbc.co",
        "bbc news": "bbc.co",
        "reuters": "reuters.com",
        "ap": "apnews",
        "associated press": "apnews",
        "smh": "smh.com",
        "sydney morning herald": "smh.com",
        "the age": "theage.com",
        "afr": "afr.com",
        "financial review": "afr.com",
        "canberra times": "canberratimes",
        "riotact": "riotact",
        "nine": "9news",
        "nine news": "9news",
        "seven": "7news",
        "seven news": "7news",
        "fox sports": "foxsports",
        "espn": "espn",
        "nrl": "nrl.com",
        "cricket australia": "cricket.com.au",
        "nca newswire": "news.com",
    }

    for story in stories:
        if story.source_url:
            continue

        source = story.source_name.lower().strip()

        # Try alias mapping first
        alias_match = aliases.get(source, "")

        # Normalised source for fuzzy matching
        source_norm = (source
                       .replace("the ", "")
                       .replace(" news", "")
                       .replace(" australia", "")
                       .replace(" ", "")
                       .strip())

        for title, url in url_list:
            title_lower = title.lower()
            domain = title_lower.replace(".com", "").replace(".au", "").replace(".co.uk", "").replace(".org", "").replace(".net", "")

            if alias_match and alias_match in title_lower:
                story.source_url = url
                matched += 1
                break
            elif source_norm and (source_norm in domain or domain in source_norm):
                story.source_url = url
                matched += 1
                break

    total_with_urls = sum(1 for s in stories if s.source_url)
    logger.info(f"  URLs: {total_with_urls}/{len(stories)} stories have links")
