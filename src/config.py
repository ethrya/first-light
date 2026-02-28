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

# Shared system prompt — {today} and {yesterday} are filled at runtime
SYSTEM_PROMPT = """\
You are a news researcher for a daily email newsletter called "First Light", \
read by an Australian professional in Canberra. \
Use Australian English spelling throughout (e.g. "labour", "organisation", "programme", "analysed"). \
Today's date is {today}. Yesterday's date was {yesterday}.

STRICT DATE REQUIREMENT:
- ONLY include stories that were published on {today} or {yesterday}.
- Do NOT include any story published before {yesterday}, even if it is interesting or relevant.
- Before including a story, check its publication date. If it is older than yesterday, skip it.
- If your search returns only older articles for a topic, return an empty "stories" array rather \
than including stale news.

When summarising news:
- Be concise and factual. Each story summary should be 2-3 sentences maximum.
- Focus on what happened, why it matters, and what comes next.
- Always include the source name and the URL where you found the story.
- If no qualifying stories exist for a topic, return {{"stories": []}}.
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
            "Search for stories published TODAY OR YESTERDAY about climate policy and energy "
            "transition, both in Australia and internationally. Include developments in renewable "
            "energy, emissions targets, carbon markets, or energy policy. "
            "Only include articles with a publication date of today or yesterday. "
            "Return 3-5 of the most significant fresh stories."
        ),
        max_uses=4,
    ),
    Topic(
        name="AI & Technology",
        prompt=(
            "Search for stories published TODAY OR YESTERDAY about artificial intelligence and "
            "technology. Include major product launches, research breakthroughs, regulation, "
            "and industry developments. "
            "Only include articles with a publication date of today or yesterday. "
            "Return 3-5 fresh stories."
        ),
        max_uses=4,
    ),
    Topic(
        name="Australian Politics & Public Sector",
        prompt=(
            "Search for Australian politics and public sector news published TODAY OR YESTERDAY. "
            "Include federal and state government decisions, policy announcements, "
            "parliamentary developments, and public service news. "
            "Only include articles with a publication date of today or yesterday. "
            "Return 3-5 fresh stories."
        ),
        max_uses=4,
    ),
    Topic(
        name="Top Global Stories",
        prompt=(
            "Search for the most important international news stories published TODAY OR YESTERDAY. "
            "Cover geopolitics, economics, conflict, diplomacy, and major world events. "
            "Exclude stories already covered under climate, AI, or Australian politics. "
            "Only include articles with a publication date of today or yesterday. "
            "Return 3-5 fresh stories."
        ),
        max_uses=4,
    ),
    Topic(
        name="Other Top Australian Stories",
        prompt=(
            "Search for significant Australian news stories published TODAY OR YESTERDAY "
            "that are not about climate/energy, AI/tech, or politics/public sector. "
            "This could include economics, business, health, culture, education, or social issues. "
            "Only include articles with a publication date of today or yesterday. "
            "Return 3-5 fresh stories."
        ),
        max_uses=3,
    ),
    Topic(
        name="Sports",
        prompt=(
            "Search for the very latest news about these three teams/sports, "
            "published TODAY OR YESTERDAY: "
            "1) Middlesbrough FC (English Championship football), "
            "2) Canberra Raiders (NRL rugby league), "
            "3) Australia's men's cricket team. "
            "For each, find the most recent match result, upcoming fixture, "
            "or significant transfer, selection, or injury news. "
            "Only include articles with a publication date of today or yesterday. "
            "Return 2-3 fresh stories per team."
        ),
        max_uses=5,
    ),
]

# ---------------------------------------------------------------------------
# Email settings
# ---------------------------------------------------------------------------

EMAIL_SUBJECT_TEMPLATE = "First Light \u2014 {date}"
