"""
First Light Newsletter — main orchestrator.

Fetches RSS feeds, curates stories with Claude, builds an HTML email, and sends it.
"""

import logging
import os
import sys
from datetime import datetime, timedelta, timezone

import anthropic
from google import genai

from .config import EMAIL_SUBJECT_TEMPLATE, TOPICS
from .dedup import dedup_raw_articles, dedup_stories
from .email_builder import build_email_html, build_plain_text
from .email_sender import send_newsletter
from .feeds import FEEDS
from .news_fetcher import curate_with_claude
from .rss_fetcher import fetch_rss_articles
from .weather import fetch_canberra_weather

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Canberra is AEST (UTC+10) / AEDT (UTC+11). Use +10 as base —
# the date will be correct either way.
AEST = timezone(timedelta(hours=10))


def main() -> None:
    today_aest = datetime.now(AEST).date()
    today_long = today_aest.strftime("%A, %-d %B %Y")   # e.g. "Friday, 28 February 2026"
    today_short = today_aest.strftime("%-d %B %Y")       # e.g. "28 February 2026"
    today_day = today_aest.strftime("%a")                 # e.g. "Sun"

    logger.info(f"Generating First Light for {today_long}")

    # ------------------------------------------------------------------
    # Validate environment
    # ------------------------------------------------------------------
    required = ["GOOGLE_API_KEY", "ANTHROPIC_API_KEY", "GMAIL_ADDRESS", "GMAIL_APP_PASSWORD"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        logger.error(f"Missing environment variables: {', '.join(missing)}")
        sys.exit(1)

    recipient = os.environ.get("RECIPIENT_EMAIL", "ethanryan9@gmail.com")

    # ------------------------------------------------------------------
    # Step 1: Fetch RSS feeds
    # ------------------------------------------------------------------
    logger.info("Fetching RSS feeds...")
    articles_by_topic = {}
    for topic in TOPICS:
        feed_urls = FEEDS.get(topic.name, [])
        if feed_urls:
            raw = fetch_rss_articles(
                topic.name, feed_urls, cutoff_hours=topic.cutoff_hours
            )
            articles_by_topic[topic.name] = dedup_raw_articles(raw)
        else:
            articles_by_topic[topic.name] = []
            logger.warning(f"  No feeds configured for {topic.name}")

    total_articles = sum(len(a) for a in articles_by_topic.values())
    logger.info(f"Total RSS articles after dedup: {total_articles}")

    # ------------------------------------------------------------------
    # Step 2: Fetch Canberra weather
    # ------------------------------------------------------------------
    weather = fetch_canberra_weather()
    if weather:
        logger.info(f"Weather: {weather}")
    else:
        logger.warning("Weather fetch returned empty")

    # ------------------------------------------------------------------
    # Step 3: Curate with Claude (grounding fallback handled inside)
    # ------------------------------------------------------------------
    gemini_client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    claude_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    stories_by_topic, intro, also_interesting = curate_with_claude(
        claude_client, articles_by_topic, today_aest, gemini_client
    )

    # ------------------------------------------------------------------
    # Step 4: Cross-topic deduplication
    # ------------------------------------------------------------------
    all_stories = [s for sl in stories_by_topic.values() for s in sl]
    deduped = dedup_stories(all_stories)
    stories_by_topic = {}
    for s in deduped:
        stories_by_topic.setdefault(s.topic, []).append(s)

    total = sum(len(s) for s in stories_by_topic.values())
    logger.info(f"Total curated stories after dedup: {total}")

    if total == 0:
        logger.warning("No stories after curation. Sending minimal newsletter.")

    # ------------------------------------------------------------------
    # Step 5: Build and send email
    # ------------------------------------------------------------------
    html_body = build_email_html(
        stories_by_topic, today_long,
        intro=intro, weather=weather, also_interesting=also_interesting,
    )
    plain_body = build_plain_text(
        stories_by_topic, today_long,
        intro=intro, weather=weather, also_interesting=also_interesting,
    )
    subject = EMAIL_SUBJECT_TEMPLATE.format(day=today_day, date=today_short)

    ok = send_newsletter(subject, html_body, plain_body, recipient)
    if ok:
        logger.info("Newsletter sent successfully.")
    else:
        logger.error("Failed to send newsletter.")
        sys.exit(1)


if __name__ == "__main__":
    main()
