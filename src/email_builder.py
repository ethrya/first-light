"""
Builds the HTML and plain-text email from structured story data.

All CSS is inline for email client compatibility (Outlook, Gmail, Apple Mail).
Layout uses tables for maximum cross-client support.
"""

from .news_fetcher import Story


def build_email_html(
    stories_by_topic: dict[str, list[Story]],
    today_str: str,
    intro: str = "",
) -> str:
    """Build the complete HTML email."""
    intro_html = _build_intro(intro)
    top = _select_top_stories(stories_by_topic)
    top_headlines = {s.headline for s in top}
    top_stories_html = _render_top_stories(top)
    topic_sections_html = _build_topic_sections(stories_by_topic, exclude=top_headlines)

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
            </td>
          </tr>

          <!-- Intro paragraph -->
{intro_html}
          <!-- Top Stories -->
          <tr>
            <td style="padding:24px 24px 20px;">
              <h2 style="margin:0 0 16px; color:#1a1a2e; font-size:20px;
                         border-bottom:2px solid #f0c040; padding-bottom:8px;">
                Top Stories
              </h2>
              {top_stories_html}
            </td>
          </tr>

          <!-- Topic Sections -->
{topic_sections_html}

          <!-- Footer -->
          <tr>
            <td style="background-color:#1a1a2e; padding:20px 24px; text-align:center;">
              <p style="margin:0; color:#888888; font-size:12px;">
                First Light is generated daily using AI-powered news search.
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
    stories_by_topic: dict[str, list[Story]],
    today_str: str,
    intro: str = "",
) -> str:
    """Build a plain-text version for email clients that don't render HTML."""
    lines = [f"FIRST LIGHT \u2014 {today_str}", "=" * 40, ""]

    if intro:
        lines += [intro, ""]

    # Top stories
    top = _select_top_stories(stories_by_topic)
    top_headlines = {s.headline for s in top}
    if top:
        lines.append("TOP STORIES")
        lines.append("-" * 11)
        for story in top:
            lines.append(f"* {story.headline}")
            lines.append(f"  {story.summary}")
            if story.source_url:
                lines.append(f"  {story.source_url}")
            lines.append("")
        lines.append("")

    # Per-topic sections (excluding stories already in Top Stories)
    for topic_name, stories in stories_by_topic.items():
        filtered = [s for s in stories if s.headline not in top_headlines]
        lines.append(topic_name.upper())
        lines.append("-" * len(topic_name))
        if not filtered:
            lines.append("No additional stories available today.")
        else:
            for story in filtered:
                lines.append(f"* {story.headline}")
                lines.append(f"  {story.summary}")
                if story.source_url:
                    lines.append(f"  {story.source_url}")
                lines.append("")
        lines.append("")

    lines.append("---")
    lines.append(
        "First Light is generated daily using AI-powered news search. "
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


def _select_top_stories(stories_by_topic: dict[str, list[Story]]) -> list[Story]:
    """Pick the 3 highest-importance stories across all topics."""
    all_stories: list[Story] = []
    for topic_stories in stories_by_topic.values():
        all_stories.extend(topic_stories)

    rank = {"high": 0, "medium": 1, "low": 2}
    all_stories.sort(key=lambda s: rank.get(s.importance, 1))
    return all_stories[:3]


def _render_top_stories(top: list[Story]) -> str:
    if not top:
        return (
            '<p style="color:#666; font-style:italic;">'
            "No top stories available today.</p>"
        )

    parts: list[str] = []
    for story in top:
        headline_html = _headline_link(story, font_size=16)
        parts.append(
            f'<div style="margin-bottom:14px;">'
            f'<p style="margin:0 0 4px; font-size:16px; font-weight:600; '
            f'color:#1a1a2e;">{headline_html}</p>'
            f'<p style="margin:0; font-size:14px; color:#444; line-height:1.4;">'
            f"{_esc(story.summary)}</p>"
            f"</div>"
        )
    return "\n              ".join(parts)


def _build_topic_sections(
    stories_by_topic: dict[str, list[Story]],
    exclude: set[str] | None = None,
) -> str:
    sections: list[str] = []
    bg_colours = ["#ffffff", "#f9f9f9"]
    excluded = exclude or set()

    for i, (topic_name, stories) in enumerate(stories_by_topic.items()):
        bg = bg_colours[i % 2]
        filtered = [s for s in stories if s.headline not in excluded]

        if not filtered:
            body = (
                '<p style="color:#666; font-style:italic;">'
                "No additional stories available for this topic today.</p>"
            )
        else:
            story_parts: list[str] = []
            for story in filtered:
                headline_html = _headline_link(story, font_size=15)
                story_parts.append(
                    f'<div style="margin-bottom:12px;">'
                    f'<p style="margin:0 0 2px; font-size:15px; font-weight:600; '
                    f'color:#1a1a2e;">{headline_html}</p>'
                    f'<p style="margin:0; font-size:13px; color:#444; '
                    f'line-height:1.4;">{_esc(story.summary)}</p>'
                    f"</div>"
                )
            body = "\n              ".join(story_parts)

        sections.append(
            f'          <tr>\n'
            f'            <td style="padding:20px 24px; background-color:{bg};">\n'
            f'              <h2 style="margin:0 0 12px; color:#1a1a2e; font-size:18px; '
            f'border-bottom:1px solid #ddd; padding-bottom:6px;">'
            f"{_esc(topic_name)}</h2>\n"
            f"              {body}\n"
            f"            </td>\n"
            f"          </tr>"
        )
    return "\n".join(sections)


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


def _esc(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
