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

    prompt = (
        f"Today is {today}.\n\n"
        "Based on these top news stories from overnight and this morning, write a short, "
        "conversational intro paragraph (2-4 sentences) for a morning email newsletter "
        "called 'First Light'.\n\n"
        "Guidelines:\n"
        "- Write in a direct, collegial tone — like a knowledgeable colleague giving a "
        "quick briefing over coffee.\n"
        "- Mention 3-5 of the most significant stories by name.\n"
        "- Use Australian English spelling throughout.\n"
        "- Do not use bullet points or lists.\n"
        "- Do not open with a greeting such as 'Good morning'.\n"
        "- Dive straight into the news.\n\n"
        f"Today's top stories:\n{stories_text}\n\n"
        "Write only the paragraph — no headings, no sign-off, no other commentary."
    )

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=300,
                temperature=0.4,
            ),
        )
        if response.text:
            return response.text.strip()
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
    _enrich_with_grounding(stories, grounding_urls)

    return stories


def _parse_response(response, topic_name: str) -> list[Story]:
    """Extract the JSON stories array from the Gemini response text."""
    raw = getattr(response, "text", None)
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


def _safe_json_loads(raw: str, topic_name: str) -> dict | None:
    """Try to parse JSON, with a fallback that isolates the first JSON object."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Fallback: find the outermost { … }
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(raw[start:end])
        except json.JSONDecodeError:
            pass

    logger.error(f"Failed to parse JSON for {topic_name}: {raw[:200]}")
    return None


def _extract_grounding_urls(response) -> dict[str, str]:
    """Extract source URLs from Gemini grounding metadata.

    Returns a mapping of title → URL.
    """
    urls: dict[str, str] = {}
    try:
        chunks = response.candidates[0].grounding_metadata.grounding_chunks
        for chunk in (chunks or []):
            if chunk.web and chunk.web.uri:
                title = chunk.web.title or ""
                urls[title] = chunk.web.uri
    except (AttributeError, IndexError):
        pass
    return urls


def _enrich_with_grounding(stories: list[Story], grounding_urls: dict[str, str]) -> None:
    """Fill in missing source URLs using grounding metadata."""
    for story in stories:
        if story.source_url:
            continue
        for title, url in grounding_urls.items():
            if (story.headline.lower()[:30] in title.lower()
                    or story.source_name.lower() in title.lower()):
                story.source_url = url
                break
