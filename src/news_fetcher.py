"""
Curates news stories using Claude as the primary editorial engine.

Claude receives the full RSS article pool and returns a complete newsletter
structure in one call: intro, tiered stories per section, and an
"Also Interesting" pick.

For topics with use_grounding_fallback=True (Canberra & Sports), Gemini
grounded search supplements thin RSS coverage before sending to Claude.
"""

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import anthropic
from google import genai
from google.genai import types

from .config import (
    CLAUDE_MODEL,
    CLAUDE_MAX_TOKENS,
    CLAUDE_CURATION_SYSTEM_PROMPT,
    GEMINI_MODEL,
    GROUNDING_SYSTEM_PROMPT,
    PRESCREEN_SYSTEM_PROMPT,
    TOPICS,
    Topic,
)
from .dedup import dedup_raw_articles
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
    tier: int = 2   # 1=must-read, 2=main, 3=brief


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def curate_with_claude(
    anthropic_client: anthropic.Anthropic,
    articles_by_topic: dict,
    today_date: date,
    gemini_client: genai.Client,
) -> tuple:
    """Curate the full newsletter with a single Claude API call.

    Returns (stories_by_topic, intro_text, also_interesting_story).
    """
    today = today_date.strftime("%A, %-d %B %Y")
    yesterday = (today_date - timedelta(days=1)).strftime("%A, %-d %B %Y")

    # ------------------------------------------------------------------
    # Step 1: Grounding fallback for thin topics
    # ------------------------------------------------------------------
    for topic in TOPICS:
        if not topic.use_grounding_fallback:
            continue
        pool = articles_by_topic.get(topic.name, [])
        if len(pool) < 2:
            logger.info(
                f"  Grounding fallback for {topic.name} "
                f"({len(pool)} RSS articles)"
            )
            grounded = _fetch_grounded_topic(
                gemini_client, topic, today, yesterday,
                existing_headlines=[a.title for a in pool],
            )
            converted = [
                _grounded_story_to_raw_article(s, topic.name)
                for s in grounded
            ]
            articles_by_topic[topic.name] = pool + converted

    # ------------------------------------------------------------------
    # Step 2: Dedup merged pool per topic
    # ------------------------------------------------------------------
    for topic_name in articles_by_topic:
        articles_by_topic[topic_name] = dedup_raw_articles(
            articles_by_topic[topic_name]
        )

    # ------------------------------------------------------------------
    # Step 3: Gemini pre-screen — pick top articles per topic
    # ------------------------------------------------------------------
    for topic in TOPICS:
        pool = articles_by_topic.get(topic.name, [])
        keep = topic.max_stories * 3  # e.g. max 4 stories → keep top 12
        if len(pool) <= keep:
            continue  # small enough already
        screened = _prescreen_topic(gemini_client, topic, pool, keep)
        articles_by_topic[topic.name] = screened

    # ------------------------------------------------------------------
    # Step 4: Build flat article list with input_index
    # ------------------------------------------------------------------
    all_articles: list[RawArticle] = []

    for topic in TOPICS:
        pool = articles_by_topic.get(topic.name, [])
        all_articles.extend(pool)

    logger.info(f"  Total articles in Claude pool: {len(all_articles)}")

    # Build lookup: input_index → RawArticle
    index_map = {i: a for i, a in enumerate(all_articles)}

    # ------------------------------------------------------------------
    # Step 5: Format user message for Claude
    # ------------------------------------------------------------------
    user_message = _build_user_message(all_articles, today)

    # ------------------------------------------------------------------
    # Step 6: Claude API call
    # ------------------------------------------------------------------
    try:
        message = anthropic_client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=CLAUDE_MAX_TOKENS,
            system=CLAUDE_CURATION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        raw = message.content[0].text
        usage = message.usage
        # Per-MTok rates: (input, output)
        _RATES = {"haiku": (1.0, 5.0), "sonnet": (3.0, 15.0), "opus": (15.0, 75.0)}
        rate = next(
            (v for k, v in _RATES.items() if k in CLAUDE_MODEL), (3.0, 15.0)
        )
        cost = (usage.input_tokens * rate[0] + usage.output_tokens * rate[1]) / 1_000_000
        logger.info(
            f"  Claude response: {len(raw)} chars, "
            f"stop_reason={message.stop_reason}"
        )
        logger.info(
            f"  Claude [{CLAUDE_MODEL}] tokens: {usage.input_tokens} in, "
            f"{usage.output_tokens} out — ${cost:.4f}"
        )
    except Exception as exc:
        logger.error(f"Claude API error: {exc}")
        return {}, "", None

    # ------------------------------------------------------------------
    # Step 7: Parse and validate response
    # ------------------------------------------------------------------
    data = _safe_json_loads(raw, "Claude curation")
    if data is None:
        logger.error("Failed to parse Claude response as JSON")
        return {}, "", None

    intro = (data.get("intro") or "").strip()

    # Build display_name → canonical topic name map
    display_to_name = {t.display_name or t.name: t.name for t in TOPICS}

    stories_by_topic: dict = {}
    tier1_count = 0

    for section in data.get("sections", []):
        display = section.get("topic", "")
        topic_name = display_to_name.get(display, display)

        for item in section.get("stories", []):
            story = _validate_story_item(item, index_map, topic_name)
            if story is None:
                continue

            # Enforce Tier 1 cap of 3 across all sections
            if story.tier == 1:
                if tier1_count >= 3:
                    story.tier = 2
                    story.importance = "medium"
                else:
                    tier1_count += 1

            stories_by_topic.setdefault(topic_name, []).append(story)

    # Log tier distribution
    tier_counts = {1: 0, 2: 0, 3: 0}
    for stories in stories_by_topic.values():
        for s in stories:
            tier_counts[s.tier] = tier_counts.get(s.tier, 0) + 1
    logger.info(f"  Tier distribution: {tier_counts}")

    # Parse also_interesting
    also_interesting: Optional[Story] = None
    ai_item = data.get("also_interesting")
    if ai_item:
        also_interesting = _validate_story_item(
            ai_item, index_map, "also_interesting"
        )
        if also_interesting:
            also_interesting.tier = 2  # render like a Tier 2 story

    return stories_by_topic, intro, also_interesting


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _grounded_story_to_raw_article(story: Story, topic_name: str) -> RawArticle:
    """Convert a Gemini-grounded Story into a RawArticle for the Claude pool."""
    return RawArticle(
        title=story.headline,
        url=story.source_url,
        source_name=story.source_name,
        published=datetime.now(timezone.utc),
        summary=story.summary,
        topic=topic_name,
    )


def _prescreen_topic(
    gemini_client: genai.Client,
    topic: Topic,
    articles: list,
    keep: int,
) -> list:
    """Use Gemini Flash to pick the top `keep` articles by newsworthiness."""
    # Build lightweight article list (title + short summary only)
    lines = []
    for i, a in enumerate(articles):
        summary = (a.summary[:150] if a.summary else "").replace("\n", " ")
        lines.append(f"[{i}] {a.title}\n{summary}")

    dn = topic.display_name or topic.name
    prompt = (
        f"Topic: {dn}\n"
        f"Select the {keep} most newsworthy articles.\n\n"
        + "\n\n".join(lines)
    )

    try:
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=PRESCREEN_SYSTEM_PROMPT,
                temperature=0.0,
                max_output_tokens=1024,
                response_mime_type="application/json",
            ),
        )
        raw = getattr(response, "text", "") or ""
        raw = raw.strip()

        # Extract array — Gemini may return object wrapper or add comments
        import re
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start >= 0 and end > start:
            array_str = raw[start:end]
        else:
            array_str = raw
        # Strip any non-numeric junk between numbers (comments, labels)
        numbers = re.findall(r'\d+', array_str)
        indices = [int(n) for n in numbers]
        if not indices:
            raise ValueError(f"No indices found in: {raw[:100]}")

        # Filter to valid indices within range
        valid = [idx for idx in indices if isinstance(idx, int) and 0 <= idx < len(articles)]
        selected = [articles[idx] for idx in valid[:keep]]

        logger.info(
            f"  Pre-screen {dn}: {len(articles)} → {len(selected)} articles"
        )
        return selected

    except Exception as exc:
        # On any failure, fall back to recency cap
        logger.warning(
            f"  Pre-screen failed for {dn}: {exc} — "
            f"falling back to first {keep}"
        )
        return articles[:keep]


def _build_user_message(all_articles: list, today: str) -> str:
    """Build the user message for the Claude curation call."""
    lines: list[str] = [f"Today is {today}.\n"]

    lines.append("ARTICLE POOL:")
    for i, a in enumerate(all_articles):
        pub_str = a.published.strftime("%d %b")
        summary = (a.summary[:150] if a.summary else "").replace("\n", " ")
        lines.append(
            f"\n[{i}] {a.topic} | {a.source_name} | {pub_str}\n"
            f"{a.title} | {a.url}\n"
            f"{summary}"
        )

    lines.append("\n\nEDITORIAL GUIDANCE PER SECTION:")
    for topic in TOPICS:
        dn = topic.display_name or topic.name
        lines.append(f"- {dn} (max {topic.max_stories}): {topic.prompt}")

    lines.append(
        "\n\nReturn a JSON object with this exact schema:\n"
        "{\n"
        '  "intro": "2-4 sentence editorial intro paragraph",\n'
        '  "sections": [\n'
        '    {\n'
        '      "topic": "<display_name from guidance above>",\n'
        '      "stories": [\n'
        '        {\n'
        '          "input_index": <integer from article pool>,\n'
        '          "tier": <1, 2, or 3>,\n'
        '          "headline": "...",\n'
        '          "summary": "...",\n'
        '          "source_name": "copied verbatim from pool",\n'
        '          "source_url": "copied verbatim from pool"\n'
        "        }\n"
        "      ]\n"
        "    }\n"
        "  ],\n"
        '  "also_interesting": {\n'
        '    "input_index": <integer>,\n'
        '    "headline": "...",\n'
        '    "summary": "...",\n'
        '    "source_name": "...",\n'
        '    "source_url": "..."\n'
        "  }\n"
        "}\n"
        "Return ONLY valid JSON. No markdown fencing."
    )

    return "\n".join(lines)


def _validate_story_item(
    item: dict,
    index_map: dict,
    topic_name: str,
) -> Optional[Story]:
    """Validate a story item from Claude's response.

    Returns a Story if valid, None if the input_index is invalid.
    Uses the pool URL as ground truth on URL mismatch (don't drop).
    """
    idx = item.get("input_index")
    if idx is None or idx not in index_map:
        logger.warning(
            f"  Dropped story (invalid input_index={idx}): "
            f"{item.get('headline', '')!r}"
        )
        return None

    source_article = index_map[idx]
    claimed_url = item.get("source_url", "")

    if claimed_url and claimed_url != source_article.url:
        logger.debug(
            f"  URL mismatch for [{idx}] — using pool URL as ground truth"
        )

    tier = max(1, min(3, int(item.get("tier", 2))))
    importance = "high" if tier == 1 else "medium" if tier == 2 else "low"

    return Story(
        headline=item.get("headline", source_article.title),
        summary=item.get("summary", ""),
        source_name=item.get("source_name") or source_article.source_name,
        source_url=source_article.url,  # always use pool URL
        importance=importance,
        topic=topic_name,
        tier=tier,
    )


# ---------------------------------------------------------------------------
# Grounding fallback (Canberra & Sports only)
# ---------------------------------------------------------------------------


def _fetch_grounded_topic(
    client: genai.Client,
    topic: Topic,
    today: str,
    yesterday: str,
    existing_headlines: list,
) -> list:
    """Search Google via Gemini grounding for a topic, avoiding duplicates.

    Stories without a matched grounding URL are dropped.
    """
    system = GROUNDING_SYSTEM_PROMPT.format(today=today, yesterday=yesterday)

    prompt_parts = [topic.prompt]
    if existing_headlines:
        prompt_parts.append(
            "\n\nI already have these stories from RSS feeds:\n"
            + "\n".join(f"- {h}" for h in existing_headlines)
            + "\n\nFind additional stories NOT already covered above."
        )
    prompt = "\n".join(prompt_parts)

    search_prompt = (
        f"Search for the latest news about {topic.name} published today or "
        f"yesterday. {prompt}"
    )

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=search_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.1,
                max_output_tokens=8192,
            ),
        )
    except Exception as exc:
        logger.error(f"Gemini grounding error for {topic.name}: {exc}")
        return []

    stories = _parse_grounded_response(response, topic.name)

    _enrich_with_grounding_supports(response, stories)
    grounding_urls = _extract_grounding_urls(response)
    _enrich_with_grounding_domain(stories, grounding_urls)

    with_urls = [s for s in stories if s.source_url]
    dropped = len(stories) - len(with_urls)
    if dropped:
        logger.info(f"  Grounding: dropped {dropped} stories without URLs")
    logger.info(
        f"  Grounding: {len(with_urls)} stories with URLs for {topic.name}"
    )
    return with_urls


# ---------------------------------------------------------------------------
# Response parsing (grounding path)
# ---------------------------------------------------------------------------


def _parse_grounded_response(response, topic_name: str) -> list:
    """Extract the JSON stories array from the Gemini grounding response."""
    raw = _extract_model_text(response)
    if not raw:
        logger.warning(f"Empty grounding response for {topic_name}")
        return []

    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]).strip()

    data = _safe_json_loads(raw, topic_name)
    if data is None:
        return []

    stories: list = []
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
    """Extract only the model-generated text from a Gemini response."""
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


def _extract_grounding_urls(response) -> dict:
    """Extract source URLs from Gemini grounding metadata."""
    urls: dict = {}
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


def _enrich_with_grounding_supports(response, stories: list) -> None:
    """Map stories to URLs using grounding_supports segment data."""
    try:
        metadata = response.candidates[0].grounding_metadata
        if not metadata:
            return

        chunks = getattr(metadata, "grounding_chunks", None) or []
        supports = getattr(metadata, "grounding_supports", None) or []

        if not chunks or not supports:
            return

        segment_urls: list = []
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


def _enrich_with_grounding_domain(stories: list, grounding_urls: dict) -> None:
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
