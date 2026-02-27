"""
First Light Newsletter Configuration

Edit the TOPICS list below to add, remove, or reorder newsletter sections.
Each topic needs:
  - name: Section heading in the email
  - prompt: Instructions for what to search and summarise
  - max_uses: Maximum web searches per topic (2-5)
"""

from dataclasses import dataclass


@dataclass
class Topic:
    name: str
    prompt: str
    max_uses: int = 3


# ---------------------------------------------------------------------------
# Anthropic API settings
# ---------------------------------------------------------------------------

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096

# Biases web search results towards Australia
USER_LOCATION = {
    "type": "approximate",
    "city": "Canberra",
    "region": "Australian Capital Territory",
    "country": "AU",
    "timezone": "Australia/Sydney",
}

# Shared system prompt — {today} is filled at runtime
SYSTEM_PROMPT = """\
You are a news researcher for a daily email newsletter called "First Light", \
read by an Australian professional in Canberra. \
Use Australian English spelling throughout (e.g. "labour", "organisation", "programme", "analysed"). \
Today's date is {today}.

When summarising news:
- Be concise and factual. Each story summary should be 2-3 sentences maximum.
- Focus on what happened, why it matters, and what comes next.
- Always include the source name and the URL where you found the story.
- Prioritise stories from the last 24 hours. If nothing significant happened, say so briefly.
- Format your response as a JSON object with this structure:

{{
  "stories": [
    {{
      "headline": "Short headline",
      "summary": "2-3 sentence summary of the story.",
      "source_name": "Name of Publication",
      "source_url": "https://full-url-to-article",
      "importance": "high" | "medium" | "low"
    }}
  ]
}}

Return ONLY valid JSON. No markdown fencing, no commentary outside the JSON.\
"""

# ---------------------------------------------------------------------------
# Topics — edit this list to change newsletter sections
# ---------------------------------------------------------------------------

TOPICS = [
    Topic(
        name="Climate Policy & Energy Transition",
        prompt=(
            "Search for today's top stories about climate policy and energy transition, "
            "both in Australia and internationally. Include any developments in renewable energy, "
            "emissions targets, carbon markets, or energy policy. "
            "Return 3-5 of the most significant stories."
        ),
        max_uses=4,
    ),
    Topic(
        name="AI & Technology",
        prompt=(
            "Search for today's top stories about artificial intelligence and technology. "
            "Include major product launches, research breakthroughs, regulation, "
            "and industry developments. Return 3-5 stories."
        ),
        max_uses=4,
    ),
    Topic(
        name="Australian Politics & Public Sector",
        prompt=(
            "Search for today's top Australian politics and public sector news. "
            "Include federal and state government decisions, policy announcements, "
            "parliamentary developments, and public service news. Return 3-5 stories."
        ),
        max_uses=4,
    ),
    Topic(
        name="Top Global Stories",
        prompt=(
            "Search for the most important international news stories from the past 24 hours. "
            "Cover geopolitics, economics, conflict, diplomacy, and major world events. "
            "Exclude stories already covered under climate, AI, or Australian politics. "
            "Return 3-5 stories."
        ),
        max_uses=4,
    ),
    Topic(
        name="Other Top Australian Stories",
        prompt=(
            "Search for other significant Australian news stories from the past 24 hours "
            "that are not about climate/energy, AI/tech, or politics/public sector. "
            "This could include economics, business, health, culture, education, or social issues. "
            "Return 3-5 stories."
        ),
        max_uses=3,
    ),
    Topic(
        name="Sports",
        prompt=(
            "Search for the latest news about these three teams/sports: "
            "1) Middlesbrough FC (English Championship football), "
            "2) Canberra Raiders (NRL rugby league), "
            "3) Australia's men's cricket team. "
            "For each, find the most recent match result or upcoming fixture, "
            "plus any significant transfer, selection, or injury news. "
            "Return 2-3 stories per team."
        ),
        max_uses=5,
    ),
]

# ---------------------------------------------------------------------------
# Email settings
# ---------------------------------------------------------------------------

EMAIL_SUBJECT_TEMPLATE = "First Light \u2014 {date}"
