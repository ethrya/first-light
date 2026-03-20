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
                max_output_tokens=500,
                temperature=0.4,
            ),
        )
        # Extract text from all parts (model may split across multiple parts)
        intro_text = ""
        try:
            parts_text = []
            for part in response.candidates[0].content.parts:
                if hasattr(part, "text") and part.text:
                    parts_text.append(part.text)
            intro_text = " ".join(parts_text).strip()
        except (AttributeError, IndexError):
            intro_text = (response.text or "").strip()

        if intro_text:
            logger.info(f"Intro generated: {intro_text[:80]}...")
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

    # Supplement missing source URLs from grounding metadata
    grounding_urls = _extract_grounding_urls(response)
    if grounding_urls:
        for title, url in list(grounding_urls.items())[:5]:
            logger.debug(f"  Grounding: {title!r} → {url[:80]}")
    _enrich_with_grounding(stories, grounding_urls)

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


def _enrich_with_grounding(stories: list[Story], grounding_urls: dict[str, str]) -> None:
    """Fill in source URLs from grounding metadata.

    Grounding chunk titles are typically just domain names (e.g. 'theguardian.com').
    We match by normalising the story's source_name to a domain-like string.
    """
    if not grounding_urls:
        logger.warning("No grounding URLs available")
        return

    logger.info(f"Grounding URLs available: {len(grounding_urls)}")
    url_list = list(grounding_urls.items())
    matched = 0

    for story in stories:
        source = story.source_name.lower()
        # Normalise source name to match domain-style titles
        # "The Guardian" → "guardian", "SBS News" → "sbs", "ABC News" → "abc"
        source_norm = (source
                       .replace("the ", "")
                       .replace(" news", "")
                       .replace(" australia", "")
                       .replace(" ", "")
                       .strip())

        best_url = ""
        best_score = 0

        for title, url in url_list:
            title_lower = title.lower().replace(".com", "").replace(".au", "").replace(".co.uk", "")
            score = 0

            # Domain-style matching: "theguardian" contains "guardian"
            if source_norm and (source_norm in title_lower or title_lower in source_norm):
                score += 3

            # Also check full source name
            if source and source in title_lower:
                score += 3

            if score > best_score:
                best_score = score
                best_url = url

        if best_url and best_score >= 3:
            story.source_url = best_url
            matched += 1

    logger.info(f"Matched {matched}/{len(stories)} stories with grounding URLs")
