"""
Fetches news for each topic using the Anthropic API with web search.
Returns structured story data with source links.
"""

import json
import logging
from dataclasses import dataclass
from datetime import date, timedelta

import anthropic

from .config import MODEL, MAX_TOKENS, SYSTEM_PROMPT, TOPICS, USER_LOCATION, Topic

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
    client: anthropic.Anthropic,
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
    client: anthropic.Anthropic,
    stories_by_topic: dict[str, list[Story]],
    today: str,
) -> str:
    """Generate a short, conversational intro paragraph summarising the top stories.

    Makes a single API call without web search — Claude writes from the story
    headlines already gathered.  Returns an empty string on failure.
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
        response = client.messages.create(
            model=MODEL,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        for block in response.content:
            if getattr(block, "type", None) == "text":
                return block.text.strip()
    except anthropic.APIError as exc:
        logger.error(f"API error generating intro: {exc}")
    except anthropic.APIConnectionError as exc:
        logger.error(f"Connection error generating intro: {exc}")

    return ""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _fetch_topic(
    client: anthropic.Anthropic,
    topic: Topic,
    today: str,
    yesterday: str,
) -> list[Story]:
    """Make a single API call with web search for one topic."""
    system = SYSTEM_PROMPT.format(today=today, yesterday=yesterday)

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": topic.prompt}],
            tools=[
                {
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": topic.max_uses,
                    "user_location": USER_LOCATION,
                }
            ],
        )
    except anthropic.APIError as exc:
        logger.error(f"API error fetching {topic.name}: {exc}")
        return []
    except anthropic.APIConnectionError as exc:
        logger.error(f"Connection error fetching {topic.name}: {exc}")
        return []

    stories = _parse_response(response, topic.name)

    # Use citation metadata to fill in any missing source URLs
    citation_urls = _extract_citation_urls(response)
    _enrich_with_citations(stories, citation_urls)

    return stories


def _parse_response(response, topic_name: str) -> list[Story]:
    """Extract the JSON stories array from Claude's response."""
    text_blocks = [
        block for block in response.content
        if getattr(block, "type", None) == "text"
    ]
    if not text_blocks:
        logger.warning(f"No text blocks in response for {topic_name}")
        return []

    raw = text_blocks[-1].text.strip()

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


def _extract_citation_urls(response) -> dict[str, str]:
    """Walk response content blocks and collect citation URLs.

    Returns a mapping of title/text snippets → URLs.
    """
    urls: dict[str, str] = {}
    for block in response.content:
        if not hasattr(block, "citations") or not block.citations:
            continue
        for cite in block.citations:
            if hasattr(cite, "url"):
                if hasattr(cite, "title") and cite.title:
                    urls[cite.title] = cite.url
                if hasattr(cite, "cited_text") and cite.cited_text:
                    urls[cite.cited_text[:60]] = cite.url
    return urls


def _enrich_with_citations(stories: list[Story], citation_urls: dict[str, str]) -> None:
    """Fill in missing source URLs using citation metadata."""
    for story in stories:
        if story.source_url:
            continue
        for key, url in citation_urls.items():
            headline_lower = story.headline.lower()
            if (headline_lower[:30] in key.lower()
                    or story.source_name.lower() in key.lower()):
                story.source_url = url
                break
