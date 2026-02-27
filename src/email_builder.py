"""
Builds the HTML and plain-text email from structured story data.

All CSS is inline for email client compatibility (Outlook, Gmail, Apple Mail).
Layout uses tables for maximum cross-client support.
"""

from .news_fetcher import Story


def build_email_html(stories_by_topic: dict[str, list[Story]], today_str: str) -> str:
    """Build the complete HTML email."""
    top_stories_html = _build_top_stories(stories_by_topic)
    topic_sections_html = _build_topic_sections(stories_by_topic)

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

          <!-- Top Stories -->
          <tr>
            <td style="padding:24px;">
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


def build_plain_text(stories_by_topic: dict[str, list[Story]], today_str: str) -> str:
    """Build a plain-text version for email clients that don't render HTML."""
    lines = [f"FIRST LIGHT \u2014 {today_str}", "=" * 40, ""]

    # Top stories
    top = _select_top_stories(stories_by_topic)
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

    # Per-topic sections
    for topic_name, stories in stories_by_topic.items():
        lines.append(topic_name.upper())
        lines.append("-" * len(topic_name))
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

    lines.append("---")
    lines.append(
        "First Light is generated daily using AI-powered news search. "
        "Always verify important stories with original sources."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _select_top_stories(stories_by_topic: dict[str, list[Story]]) -> list[Story]:
    """Pick the 3-5 highest-importance stories across all topics."""
    all_stories: list[Story] = []
    for topic_stories in stories_by_topic.values():
        all_stories.extend(topic_stories)

    rank = {"high": 0, "medium": 1, "low": 2}
    all_stories.sort(key=lambda s: rank.get(s.importance, 1))
    return all_stories[:5]


def _build_top_stories(stories_by_topic: dict[str, list[Story]]) -> str:
    top = _select_top_stories(stories_by_topic)

    if not top:
        return (
            '<p style="color:#666; font-style:italic;">'
            "No top stories available today.</p>"
        )

    parts: list[str] = []
    for story in top:
        link = _source_link(story, font_size=13)
        parts.append(
            f'<div style="margin-bottom:14px;">'
            f'<p style="margin:0 0 4px; font-size:16px; font-weight:600; '
            f'color:#1a1a2e;">{_esc(story.headline)}</p>'
            f'<p style="margin:0; font-size:14px; color:#444; line-height:1.4;">'
            f"{_esc(story.summary)}{link}</p>"
            f"</div>"
        )
    return "\n              ".join(parts)


def _build_topic_sections(stories_by_topic: dict[str, list[Story]]) -> str:
    sections: list[str] = []
    bg_colours = ["#ffffff", "#f9f9f9"]

    for i, (topic_name, stories) in enumerate(stories_by_topic.items()):
        bg = bg_colours[i % 2]

        if not stories:
            body = (
                '<p style="color:#666; font-style:italic;">'
                "No stories available for this topic today.</p>"
            )
        else:
            story_parts: list[str] = []
            for story in stories:
                link = _source_link(story, font_size=12)
                story_parts.append(
                    f'<div style="margin-bottom:12px;">'
                    f'<p style="margin:0 0 2px; font-size:15px; font-weight:600; '
                    f'color:#1a1a2e;">{_esc(story.headline)}</p>'
                    f'<p style="margin:0; font-size:13px; color:#444; '
                    f'line-height:1.4;">{_esc(story.summary)}{link}</p>'
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


def _source_link(story: Story, font_size: int = 12) -> str:
    """Build an HTML source link, or empty string if no URL."""
    if not story.source_url:
        return ""
    label = _esc(story.source_name) if story.source_name else "Source"
    return (
        f' <a href="{_esc(story.source_url)}" '
        f'style="color:#2a6496; text-decoration:none; font-size:{font_size}px;">'
        f"[{label}]</a>"
    )


def _esc(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
