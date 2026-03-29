"""
Fetches "What to Watch Today" — a short list of scheduled events for the day.

Uses Gemini grounded search (Google Search) to find confirmed events:
economy (RBA, ABS), parliament, national cabinet, sport fixtures, key speeches.

Returns a list of WatchItem objects, or [] on any failure.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from google import genai
from google.genai import types

from .config import GEMINI_MODEL, WATCH_TODAY_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Try these models in order — first one that works wins.
# gemini-1.5-flash supports google_search_retrieval (not google_search tool).
# gemini-2.x / 2.5.x use types.Tool(google_search=...) — try those first.
_MODEL_CANDIDATES = [
    GEMINI_MODEL,
    "gemini-2.5-pro-exp-03-25",
    "gemini-3-flash-preview",
    "gemini-2.0-flash-exp",
]

# Category display labels and ordering
_CATEGORY_LABELS: dict = {
    "economy":    "Economy",
    "parliament": "Parliament",
    "cabinet":    "Cabinet",
    "sport":      "Sport",
    "other":      "Today",
}

_CATEGORY_ORDER = ["economy", "parliament", "cabinet", "sport", "other"]


@dataclass
class WatchItem:
    category: str   # economy | parliament | cabinet | sport | other
    title: str
    detail: str
    time: str = ""  # "11:30am AEST" or ""


def fetch_watch_today(
    gemini_client: genai.Client,
    today_date,  # datetime.date
) -> list:
    """Return a sorted list of WatchItems for today, or [] on failure."""
    today_str = today_date.strftime("%A, %-d %B %Y")

    system = WATCH_TODAY_SYSTEM_PROMPT.format(today=today_str)
    search_prompt = (
        f"What is scheduled to happen in Australia today, {today_str}? "
        "Search for confirmed events: RBA interest rate decisions, ABS data "
        "releases, parliament sitting, national cabinet, sports fixtures for "
        "Canberra Raiders, Australian cricket, and Middlesbrough FC, and key "
        "political speeches or press conferences."
    )

    response = None
    for model in _MODEL_CANDIDATES:
        try:
            response = gemini_client.models.generate_content(
                model=model,
                contents=search_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.1,
                    max_output_tokens=2048,
                ),
            )
            logger.info(f"Watch Today: using model {model}")
            break
        except Exception as exc:
            if "404" in str(exc) or "NOT_FOUND" in str(exc) or "deprecated" in str(exc).lower():
                logger.info(f"Watch Today: model {model} unavailable ({exc}), trying next")
                continue
            logger.warning(f"Watch Today grounding failed on {model}: {exc}")
            return []

    if response is None:
        logger.warning("Watch Today: no available Gemini model found")
        return []

    raw = _extract_text(response)
    items = _parse_items(raw)

    # Sort by category order
    order = {cat: i for i, cat in enumerate(_CATEGORY_ORDER)}
    items.sort(key=lambda x: order.get(x.category, 99))

    logger.info(f"Watch Today: {len(items)} items found")
    for item in items:
        logger.info(f"  [{item.category}] {item.title}")

    return items


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_text(response) -> str:
    """Pull the model text from a (possibly multi-part) Gemini response."""
    try:
        parts = response.candidates[0].content.parts
        for part in parts:
            if hasattr(part, "text") and part.text and '"items"' in part.text:
                return part.text
        texts = [
            p.text for p in parts
            if hasattr(p, "text") and p.text
        ]
        return "\n".join(texts)
    except (AttributeError, IndexError):
        pass
    return getattr(response, "text", None) or ""


def _parse_items(raw: str) -> list:
    """Parse Gemini's JSON response into WatchItems."""
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]).strip()

    # Find JSON object
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start < 0 or end <= start:
        logger.warning(f"Watch Today: no JSON found in response: {raw[:200]}")
        return []

    try:
        data = json.loads(raw[start:end])
    except json.JSONDecodeError as exc:
        logger.warning(f"Watch Today: JSON parse error: {exc} — {raw[:200]}")
        return []

    items: list = []
    for item in data.get("items", []):
        title = (item.get("title") or "").strip()
        detail = (item.get("detail") or "").strip()
        if not title:
            continue
        category = (item.get("category") or "other").lower().strip()
        if category not in _CATEGORY_LABELS:
            category = "other"
        items.append(WatchItem(
            category=category,
            title=title,
            detail=detail,
            time=(item.get("time") or "").strip(),
        ))

    return items
