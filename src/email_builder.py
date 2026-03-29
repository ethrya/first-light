"""
Builds the HTML and plain-text email from structured story data.

All CSS is inline for email client compatibility (Outlook, Gmail, Apple Mail).
Layout uses tables for maximum cross-client support.
"""

from typing import Optional

from .config import TOPICS
from .news_fetcher import Story

_TOPIC_DISPLAY: dict = {t.name: t.display_name or t.name for t in TOPICS}


def build_email_html(
    stories_by_topic: dict,
    today_str: str,
    intro: str = "",
    weather: str = "",
    also_interesting: Optional[Story] = None,
) -> str:
    """Build the complete HTML email."""
    intro_html = _build_intro(intro)
    topic_sections_html = _build_topic_sections(stories_by_topic)
    also_interesting_html = _build_also_interesting(also_interesting)
    weather_html = (
        f'<p style="margin:4px 0 0; color:#aaaaaa; font-size:12px;">'
        f"{_esc(weather)}</p>"
        if weather else ""
    )

    return f"""\
<!DOCTYPE html>
<html lang="en-AU">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>First Light \u2014 {_esc(today_str)}</title>
</head>
<body style="margin:0; padding:0; background-color:#f4f4f4; font-family:Georgia, 'Times New Roman', serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="background-color:#f4f4f4;">
    <tr>
      <td align="center" style="padding:20px 10px;">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0"
               style="max-width:600px; width:100%; background-color:#ffffff;
                      border-radius:8px; overflow:hidden;">

          <!-- Header -->
          <tr>
            <td style="background-color:#1a1a2e; padding:30px 24px; text-align:center;">
              <h1 style="margin:0; color:#f0c040; font-size:28px;
                         font-weight:700; letter-spacing:1px;">
                &#9788; First Light
              </h1>
              <p style="margin:8px 0 0; color:#cccccc; font-size:14px;">
                {_esc(today_str)}
              </p>
              {weather_html}
            </td>
          </tr>

          <!-- Intro paragraph -->
{intro_html}
          <!-- Topic Sections -->
{topic_sections_html}

          <!-- Also Interesting -->
{also_interesting_html}
          <!-- Footer -->
          <tr>
            <td style="background-color:#1a1a2e; padding:20px 24px; text-align:center;">
              <p style="margin:0; color:#888888; font-size:12px;">
                First Light is generated daily using AI-powered news curation.
                Always verify important stories with original sources.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def build_plain_text(
    stories_by_topic: dict,
    today_str: str,
    intro: str = "",
    weather: str = "",
    also_interesting: Optional[Story] = None,
) -> str:
    """Build a plain-text version for email clients that don't render HTML."""
    lines = [f"FIRST LIGHT \u2014 {today_str}"]
    if weather:
        lines.append(weather)
    lines += ["=" * 40, ""]

    if intro:
        lines += [intro, ""]

    # Per-topic sections in TOPICS order
    for topic in TOPICS:
        topic_name = topic.name
        if topic_name not in stories_by_topic:
            continue
        stories = stories_by_topic[topic_name]
        display = _TOPIC_DISPLAY.get(topic_name, topic_name)
        lines.append(display.upper())
        lines.append("-" * len(display))
        if not stories:
            lines.append("No stories available today.")
        else:
            for story in stories:
                lines.append(f"* {story.headline}")
                lines.append(f"  {story.summary}")
                if story.source_url:
                    lines.append(f"  {story.source_url}")
                lines.append("")
        lines.append("")

    if also_interesting:
        lines.append("ALSO INTERESTING")
        lines.append("-" * 16)
        lines.append(f"* {also_interesting.headline}")
        lines.append(f"  {also_interesting.summary}")
        if also_interesting.source_url:
            lines.append(f"  {also_interesting.source_url}")
        lines += ["", ""]

    lines.append("---")
    lines.append(
        "First Light is generated daily using AI-powered news curation. "
        "Always verify important stories with original sources."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_intro(intro: str) -> str:
    """Render the intro paragraph row, or an empty string if there is none."""
    if not intro:
        return ""
    return (
        "          <tr>\n"
        "            <td style=\"padding:20px 24px 0; background-color:#ffffff;\">\n"
        "              <p style=\"margin:0; font-size:15px; color:#333333; "
        "line-height:1.65; font-style:italic; border-left:3px solid #f0c040; "
        "padding-left:12px;\">\n"
        f"                {_esc(intro)}\n"
        "              </p>\n"
        "            </td>\n"
        "          </tr>\n"
    )


def _build_topic_sections(stories_by_topic: dict) -> str:
    sections: list = []
    bg_colours = ["#ffffff", "#f9f9f9"]

    for i, topic in enumerate(TOPICS):
        topic_name = topic.name
        if topic_name not in stories_by_topic:
            continue
        stories = stories_by_topic[topic_name]
        display_name = _TOPIC_DISPLAY.get(topic_name, topic_name)
        bg = bg_colours[i % 2]

        if not stories:
            body = (
                '<p style="color:#666; font-style:italic;">'
                "No stories available for this topic today.</p>"
            )
        else:
            story_parts: list = []
            for story in stories:
                story_parts.append(_render_story(story))
            body = "\n              ".join(story_parts)

        sections.append(
            f"          <tr>\n"
            f"            <td style=\"padding:20px 24px; background-color:{bg};\">\n"
            f"              <h2 style=\"margin:0 0 12px; color:#1a1a2e; font-size:18px; "
            f"border-bottom:1px solid #ddd; padding-bottom:6px;\">"
            f"{_esc(display_name)}</h2>\n"
            f"              {body}\n"
            f"            </td>\n"
            f"          </tr>"
        )
    return "\n".join(sections)


def _render_story(story: Story) -> str:
    """Render a single story according to its tier."""
    if story.tier == 1:
        return _render_tier1(story)
    elif story.tier == 3:
        return _render_tier3(story)
    else:
        return _render_tier2(story)


def _render_tier1(story: Story) -> str:
    """Tier 1: must-read. Gold left border, larger text."""
    headline_html = _headline_link(story, font_size=16)
    source_tag = _source_tag(story, font_size=13)
    return (
        f'<div style="margin-bottom:16px; border-left:3px solid #f0c040; '
        f'padding-left:10px;">'
        f'<p style="margin:0 0 4px; font-size:16px; font-weight:600; '
        f'color:#1a1a2e;">{headline_html}</p>'
        f'<p style="margin:0; font-size:15px; color:#333; line-height:1.65;">'
        f"{_esc(story.summary)}{source_tag}</p>"
        f"</div>"
    )


def _render_tier2(story: Story) -> str:
    """Tier 2: main story. Standard styling."""
    headline_html = _headline_link(story, font_size=15)
    source_tag = _source_tag(story, font_size=12)
    return (
        f'<div style="margin-bottom:12px;">'
        f'<p style="margin:0 0 2px; font-size:15px; font-weight:600; '
        f'color:#1a1a2e;">{headline_html}</p>'
        f'<p style="margin:0; font-size:13px; color:#444; line-height:1.4;">'
        f"{_esc(story.summary)}{source_tag}</p>"
        f"</div>"
    )


def _render_tier3(story: Story) -> str:
    """Tier 3: brief. Bold headline + one-sentence summary."""
    headline_html = _headline_link(story, font_size=14)
    source_tag = _source_tag(story, font_size=12)
    return (
        f'<div style="margin-bottom:10px;">'
        f'<p style="margin:0 0 1px; font-size:14px; font-weight:600; '
        f'color:#1a1a2e;">{headline_html}</p>'
        f'<p style="margin:0; font-size:13px; color:#555; line-height:1.4;">'
        f"{_esc(story.summary)}{source_tag}</p>"
        f"</div>"
    )


def _build_also_interesting(story: Optional[Story]) -> str:
    """Render the Also Interesting section, or empty string if no story."""
    if not story:
        return ""
    headline_html = _headline_link(story, font_size=15)
    source_tag = _source_tag(story, font_size=12)
    return (
        "          <tr>\n"
        "            <td style=\"padding:20px 24px; background-color:#f5f0e8;\">\n"
        "              <h2 style=\"margin:0 0 12px; color:#1a1a2e; font-size:18px; "
        "font-style:italic; border-bottom:1px solid #ddd; padding-bottom:6px;\">"
        "Also Interesting</h2>\n"
        f"              <div style=\"margin-bottom:12px;\">\n"
        f"                <p style=\"margin:0 0 2px; font-size:15px; font-weight:600; "
        f"color:#1a1a2e;\">{headline_html}</p>\n"
        f"                <p style=\"margin:0; font-size:13px; color:#444; "
        f"line-height:1.4;\">{_esc(story.summary)}{source_tag}</p>\n"
        f"              </div>\n"
        "            </td>\n"
        "          </tr>\n"
    )


def _headline_link(story: Story, font_size: int = 15) -> str:
    """Render headline as a link if URL exists, otherwise plain text."""
    escaped = _esc(story.headline)
    if not story.source_url:
        return escaped
    return (
        f'<a href="{_esc(story.source_url)}" '
        f'style="color:#1a1a2e; text-decoration:none; font-size:{font_size}px;">'
        f"{escaped}</a>"
    )


def _source_tag(story: Story, font_size: int = 12) -> str:
    """Render a source attribution tag after the summary."""
    if not story.source_name:
        return ""
    label = _esc(story.source_name)
    return (
        f' <span style="color:#888; font-size:{font_size}px;">'
        f"\u2014 {label}</span>"
    )


def _esc(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
