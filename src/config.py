"""
First Light Newsletter Configuration

Edit the TOPICS list below to add, remove, or reorder newsletter sections.
Each topic needs:
  - name: Section heading in the email (must match key in feeds.py)
  - display_name: Short header used in the email (e.g. "Climate & Energy")
  - prompt: Editorial angle guidance for Claude
  - use_grounding_fallback: If True, Gemini searches Google when RSS is thin
  - max_stories: Story cap passed to Claude as editorial guidance
"""

from dataclasses import dataclass, field


@dataclass
class Topic:
    name: str
    prompt: str
    use_grounding_fallback: bool = False
    cutoff_hours: int = 36  # how far back to look in RSS feeds
    display_name: str = ""  # short section header in email
    max_stories: int = 4    # cap passed to Claude in editorial guidance


# ---------------------------------------------------------------------------
# Gemini API settings (grounding fallback only)
# ---------------------------------------------------------------------------

GEMINI_MODEL = "gemini-3-flash-preview"

# ---------------------------------------------------------------------------
# Claude API settings
# ---------------------------------------------------------------------------

CLAUDE_MODEL = "claude-sonnet-4-6"
CLAUDE_MAX_TOKENS = 8192

CLAUDE_CURATION_SYSTEM_PROMPT = """\
You are the editor of "First Light", a daily morning newsletter read by an \
Australian professional in Canberra. Your voice is dry, precise, and \
occasionally wry — the tone of a senior policy professional who reads widely \
and writes well. Australian English throughout.

BANNED PHRASES — never use these:
"in a move that", "amid growing concerns", "raises questions about", \
"in a significant development", "it remains to be seen", "going forward", \
"at the end of the day", "a number of", "landmark", "historic", "bombshell"

VARY SENTENCE LENGTH. Connect threads between stories when there's a genuine \
link — don't force it.

WHAT MAKES A STORY WORTH INCLUDING:
- Impactful: affects many people or has real-world consequences
- Significant: represents a meaningful shift, decision, or milestone
- Surprising: unexpected, counterintuitive, or breaks from the norm
- Relevant to Australian context: prioritise stories with an Australian angle \
or direct implications for Australia
- Interesting: compelling human stories, notable firsts, stories that spark \
conversation
Prefer stories that combine several of these qualities.

STORY TIERS — assign every story a tier:
- Tier 1 (2-3 stories TOTAL across ALL sections): Must-read stories. \
3-4 sentences. Give texture and voice. Connect to broader context. \
Reserve for stories that are genuinely consequential, surprising, or both.
- Tier 2 (main stories per section): 2 sentences. Informative with a touch \
of perspective. The backbone of each section.
- Tier 3 (minor/remaining): Brief item. Always include a headline field. \
The summary is one sentence maximum. \
E.g. headline: "Victoria scraps free regional rail fares", \
summary: "Citing budget pressures, the state government has ended the scheme. — Herald Sun"

INTRO: 2-4 sentences. Genuine editorial voice. Connect themes across topics \
where real threads exist. Do NOT stitch three headlines together. \
This is a paragraph that gives the reader a sense of what kind of morning it is.

ALSO INTERESTING: Pick one story from anywhere in the pool that is \
surprising, human, or memorable — the kind of thing a reader forwards to \
a friend. 2-3 sentences with slightly more colour than a Tier 2 story. \
It should feel like a reward at the end.

CRITICAL RULES:
- Reference stories by their input_index (the number in square brackets).
- Copy source_url and source_name VERBATIM from the article pool. \
Do not invent, shorten, or modify URLs.
- If a story has no URL in the pool, do not invent one — omit source_url.
- Do not include duplicate or near-duplicate stories across sections.
- Return ONLY valid JSON matching the schema in the user message. \
No markdown fencing, no commentary outside the JSON.\
"""

# System prompt for grounding fallback (Canberra & Sports only) — unchanged
GROUNDING_SYSTEM_PROMPT = """\
You are a news researcher for a daily email newsletter called "First Light", \
read by an Australian professional in Canberra. \
Use Australian English spelling throughout (e.g. "labour", "organisation", "programme", "analysed"). \
Today's date is {today}. Yesterday's date was {yesterday}.

DATE REQUIREMENT:
- Only include stories published today ({today}) or yesterday ({yesterday}).
- If your first search yields no results from today or yesterday, try different search terms — \
add today's date to your query, try a broader topic phrase, or search a different news source. \
Use all available searches to find fresh content.
- If after trying multiple searches you still cannot find stories from today or yesterday, \
include the most recent stories available and briefly note the publication date in the summary.

WRITING STYLE:
- Write punchy, direct summaries. 1-2 sentences max — no filler, no fluff.
- Lead with what happened. Add why it matters only if it's not obvious.
- Use short sentences. Prefer active voice. Cut unnecessary words.
- Headlines should be sharp and specific — not vague or generic.
- Write like a newsroom wire, not an essay.
- Include the source name for each story.
- Always set source_url to an empty string. URLs are added automatically from search metadata.
- If no qualifying stories exist for a topic, return {{"stories": []}}.
- Format your response as a JSON object with this exact structure:

{{
  "stories": [
    {{
      "headline": "Short, punchy headline",
      "summary": "1-2 sentence summary. Direct and factual.",
      "source_name": "Name of Publication",
      "source_url": "",
      "importance": "high"
    }}
  ]
}}

The importance field must be one of: "high", "medium", "low".

Return ONLY valid JSON. No markdown fencing, no commentary outside the JSON.\
"""

# System prompt for the "What to Watch Today" grounding search
WATCH_TODAY_SYSTEM_PROMPT = """\
You are a daily briefing researcher. Search the web to find what is \
SCHEDULED or CONFIRMED to happen in Australia today ({today}).

Only include items that are definitively happening today — not speculation, \
not yesterday's results, not general background.

Search for:
1. ECONOMY: RBA interest rate decision (if today is a board meeting day), \
ABS data releases (employment, CPI, GDP, retail trade, housing), \
Treasury/budget announcements
2. PARLIAMENT: Federal parliament sitting (House or Senate), Senate estimates
3. CABINET: National Cabinet or federal cabinet meetings
4. SPORT: Today's fixtures for Canberra Raiders (NRL), Australia men's \
cricket (any format), Middlesbrough FC (English Championship)
5. OTHER: Scheduled speeches or press conferences by PM, Treasurer, \
RBA Governor

Return valid JSON only — no markdown fencing, no commentary:
{{
  "items": [
    {{
      "category": "economy|parliament|cabinet|sport|other",
      "title": "Short title (e.g. \\"ABS Labour Force data\\" or \\"Raiders v Broncos\\")",
      "detail": "One sentence — what it is and why it matters",
      "time": "Time in AEST if known, otherwise empty string"
    }}
  ]
}}

If nothing confirmed for a category, omit it entirely.
If nothing found at all, return {{"items": []}}.
Return ONLY valid JSON.\
"""

# ---------------------------------------------------------------------------
# Topics — edit this list to change newsletter sections
# ---------------------------------------------------------------------------

TOPICS = [
    Topic(
        name="Other Top Australian Stories",
        display_name="Australia",
        max_stories=4,
        prompt=(
            "Economics, business, health, culture, education. Exclude "
            "climate/energy, AI/tech, and politics covered in other sections."
        ),
    ),
    Topic(
        name="Australian Politics & Public Sector",
        display_name="Australian Politics",
        max_stories=4,
        prompt=(
            "Federal and state decisions affecting everyday Australians, "
            "parliamentary developments, public service news. "
            "Skip routine press releases and minor political bickering."
        ),
    ),
    Topic(
        name="Canberra & ACT",
        display_name="Canberra",
        max_stories=5,
        prompt=(
            "ACT government decisions, local politics, community issues, "
            "infrastructure, housing, cost of living. The reader lives and "
            "works in Canberra — this section should feel substantial."
        ),
        use_grounding_fallback=True,
    ),
    Topic(
        name="Top Global Stories",
        display_name="Global",
        max_stories=4,
        prompt=(
            "Geopolitics, economics, conflict, diplomacy. Exclude climate, "
            "AI, and Australian politics already covered above. "
            "Prefer stories with Asia-Pacific relevance."
        ),
    ),
    Topic(
        name="Climate Policy & Energy Transition",
        display_name="Climate & Energy",
        max_stories=4,
        prompt=(
            "Australian climate and energy policy, major international climate "
            "targets, significant investment or divestment, breakthrough "
            "technology. Exclude routine weather unless record-breaking."
        ),
    ),
    Topic(
        name="AI & Technology",
        display_name="AI & Tech",
        max_stories=4,
        prompt=(
            "Broad-impact AI launches, research breakthroughs, regulation and "
            "policy, major funding or acquisitions, security incidents. "
            "Skip minor app updates and routine corporate earnings."
        ),
    ),
    Topic(
        name="Sports",
        display_name="Sports",
        max_stories=3,
        prompt=(
            "Boro FC (English Championship), Canberra Raiders (NRL), "
            "Australia men's cricket. Match results, fixtures, transfers, "
            "selections, injuries."
        ),
        use_grounding_fallback=True,
        cutoff_hours=48,
    ),
]

# ---------------------------------------------------------------------------
# Email settings
# ---------------------------------------------------------------------------

EMAIL_SUBJECT_TEMPLATE = "\u2600 First Light \u2014 {day} {date}"
