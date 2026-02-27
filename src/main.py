"""
First Light Newsletter — main orchestrator.

Fetches news via the Anthropic API, builds an HTML email, and sends it.
"""

import logging
import os
import sys
from datetime import datetime, timedelta, timezone

import anthropic

from .config import EMAIL_SUBJECT_TEMPLATE
from .email_builder import build_email_html, build_plain_text
from .email_sender import send_newsletter
from .news_fetcher import fetch_all_stories

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

    logger.info(f"Generating First Light for {today_long}")

    # ------------------------------------------------------------------
    # Validate environment
    # ------------------------------------------------------------------
    required = ["ANTHROPIC_API_KEY", "GMAIL_ADDRESS", "GMAIL_APP_PASSWORD"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        logger.error(f"Missing environment variables: {', '.join(missing)}")
        sys.exit(1)

    recipient = os.environ.get("RECIPIENT_EMAIL", "ethanryan9@gmail.com")

    # ------------------------------------------------------------------
    # Fetch news
    # ------------------------------------------------------------------
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
    stories_by_topic = fetch_all_stories(client, today_long)

    total = sum(len(s) for s in stories_by_topic.values())
    logger.info(f"Total stories fetched: {total}")

    if total == 0:
        logger.warning("No stories fetched for any topic. Sending minimal newsletter.")

    # ------------------------------------------------------------------
    # Build and send email
    # ------------------------------------------------------------------
    html_body = build_email_html(stories_by_topic, today_long)
    plain_body = build_plain_text(stories_by_topic, today_long)
    subject = EMAIL_SUBJECT_TEMPLATE.format(date=today_short)

    ok = send_newsletter(subject, html_body, plain_body, recipient)
    if ok:
        logger.info("Newsletter sent successfully.")
    else:
        logger.error("Failed to send newsletter.")
        sys.exit(1)


if __name__ == "__main__":
    main()
