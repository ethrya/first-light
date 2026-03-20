"""
First Light Newsletter Configuration

Edit the TOPICS list below to add, remove, or reorder newsletter sections.
Each topic needs:
  - name: Section heading in the email
  - prompt: Instructions for what to search and summarise (be specific about search terms)
  - max_uses: Kept for reference; Gemini grounding searches automatically as needed
"""

from dataclasses import dataclass


@dataclass
class Topic:
    name: str
    prompt: str
    max_uses: int = 4  # informational only with Gemini; grounding is automatic


# ---------------------------------------------------------------------------
# Gemini API settings
# ---------------------------------------------------------------------------

MODEL = "gemini-3-flash-preview"
MAX_OUTPUT_TOKENS = 4096

# Shared system prompt — {today} and {yesterday} are filled at runtime
SYSTEM_PROMPT = """\
You are a news researcher for a daily email newsletter called "First Light", \
read by an Australian professional in Canberra. \
Use Australian English spelling throughout (e.g. "labour", "organisation", "programme", "analysed"). \
Today's date is {today}. Yesterday's date was {yesterday}.

DATE REQUIREMENT:
- Only include stories published today ({today}) or yesterday ({yesterday}).
- Before including a story, check its publication date carefully.
- If your first search yields no results from today or yesterday, try different search terms — \
add today's date to your query, try a broader topic phrase, or search a different news source. \
Use all available searches to find fresh content.
- If after trying multiple searches you still cannot find stories from today or yesterday, \
include the most recent stories available and briefly note the publication date in the summary.

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
            "Search for stories published today or yesterday about climate policy and energy "
            "transition, both in Australia and internationally. "
            "Try: 'climate policy news today', 'renewable energy Australia news', "
            "'energy transition news', 'carbon emissions news today'. "
            "Include developments in renewable energy, emissions targets, carbon markets, "
            "or energy policy. Return 3-5 significant stories."
        ),
        max_uses=4,
    ),
    Topic(
        name="AI & Technology",
        prompt=(
            "Search for stories published today or yesterday about artificial intelligence "
            "and technology. "
            "Try: 'AI news today', 'artificial intelligence news', 'tech news today', "
            "and search for specific companies or products you know are newsworthy. "
            "Include major product launches, research breakthroughs, regulation, "
            "and industry developments. Return 3-5 stories."
        ),
        max_uses=4,
    ),
    Topic(
        name="Australian Politics & Public Sector",
        prompt=(
            "Search for Australian politics and public sector news published today or yesterday. "
            "Try multiple searches: 'Australia politics news today', "
            "'Australian federal government news', 'Australian parliament news', "
            "'Australia minister announcement today', 'Australian Senate news'. "
            "Include federal and state government decisions, policy announcements, "
            "parliamentary developments, and public service news. Return 3-5 stories."
        ),
        max_uses=6,
    ),
    Topic(
        name="Top Global Stories",
        prompt=(
            "Search for the most important international news published today or yesterday. "
            "Try multiple searches: 'world news today', 'international news today', "
            "'breaking news today', 'US news today', 'Europe news today', 'Asia news today'. "
            "Cover geopolitics, economics, conflict, diplomacy, and major world events. "
            "Exclude stories already covered under climate, AI, or Australian politics. "
            "Return 3-5 stories."
        ),
        max_uses=6,
    ),
    Topic(
        name="Other Top Australian Stories",
        prompt=(
            "Search for significant Australian news published today or yesterday, "
            "excluding climate/energy, AI/tech, and politics/public sector. "
            "Try: 'Australia news today', 'ABC News Australia latest', "
            "'Australian business news today', 'Australia economy news', "
            "'Australia health news today'. "
            "Include economics, business, health, culture, education, or social issues. "
            "Return 3-5 stories."
        ),
        max_uses=5,
    ),
    Topic(
        name="Canberra & ACT",
        prompt=(
            "Search for local Canberra and ACT news published today or yesterday. "
            "Try: 'Canberra news today', 'ACT government news', 'Canberra Times latest', "
            "'RiotACT news today', 'ACT politics news'. "
            "Include ACT government decisions, local politics, community issues, "
            "infrastructure, housing, cost of living, and local events. Return 2-4 stories."
        ),
        max_uses=4,
    ),
    Topic(
        name="Sports",
        prompt=(
            "Search for the latest news about these three teams/sports: "
            "1) Middlesbrough FC (English Championship football), "
            "2) Canberra Raiders (NRL rugby league), "
            "3) Australia's men's cricket team. "
            "For each, try: '[team name] news today', '[team name] latest', "
            "'[team name] match result', '[team name] news'. "
            "Find match results, upcoming fixtures, transfers, selections, or injury news. "
            "Sport doesn't happen every day — include the most recent news up to 48 hours old. "
            "Return 2-3 stories per team."
        ),
        max_uses=7,
    ),
]

# ---------------------------------------------------------------------------
# Email settings
# ---------------------------------------------------------------------------

EMAIL_SUBJECT_TEMPLATE = "First Light \u2014 {date}"
