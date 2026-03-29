"""
First Light Newsletter Configuration

Edit the TOPICS list below to add, remove, or reorder newsletter sections.
Each topic needs:
  - name: Section heading in the email (must match key in feeds.py)
  - prompt: Curation instructions — tells Gemini how to select and rank stories
  - use_grounding_fallback: If True, also searches Google when RSS is thin
"""

from dataclasses import dataclass, field


@dataclass
class Topic:
    name: str
    prompt: str
    use_grounding_fallback: bool = False


# ---------------------------------------------------------------------------
# Gemini API settings
# ---------------------------------------------------------------------------

MODEL = "gemini-3-flash-preview"
MAX_OUTPUT_TOKENS = 8192

# System prompt for curation — Gemini selects and rewrites from an RSS pool.
# {today} and {yesterday} are filled at runtime.
CURATION_SYSTEM_PROMPT = """\
You are a news editor for "First Light", a daily email newsletter read by an \
Australian professional in Canberra. You are given a pool of raw news articles \
fetched from RSS feeds. Your job is to select the most important stories and \
write sharp summaries for each.

Use Australian English spelling throughout (e.g. "labour", "organisation", \
"programme", "analysed"). Today is {today}. Yesterday was {yesterday}.

WHAT MAKES A STORY WORTH INCLUDING:
- Impactful: affects many people or has real-world consequences
- Significant: represents a meaningful shift, decision, or milestone
- Surprising: unexpected, counterintuitive, or breaks from the norm
- Relevant to Australian context: prioritise stories with an Australian angle \
or direct implications for Australia
- Interesting: compelling human stories, notable firsts, or stories that spark \
conversation
Prefer stories that combine several of these qualities. Skip routine \
announcements, incremental updates, or rehashed wire copy.

WRITING STYLE:
- Write punchy, direct summaries. 1-2 sentences max — no filler, no fluff.
- Lead with what happened. Add why it matters only if it's not obvious.
- Use short sentences. Prefer active voice. Cut unnecessary words.
- Headlines should be sharp and specific — not vague or generic.
- Write like a newsroom wire, not an essay.

CRITICAL RULES:
- You MUST copy source_url and source_name EXACTLY from the article pool. \
Do not invent, modify, or guess URLs. Use the URL from the numbered article.
- Do NOT include duplicate or near-duplicate stories. If multiple articles \
cover the same event, pick the single best one.
- Aim for the target number of stories specified in the topic prompt. Only \
return fewer if the pool genuinely doesn't have enough noteworthy material \
— not every article needs to be extraordinary, just worth a reader's time.
- Return ONLY valid JSON with this exact structure:

{{
  "stories": [
    {{
      "headline": "Short, punchy headline",
      "summary": "1-2 sentence summary. Direct and factual.",
      "source_name": "Copied from article pool",
      "source_url": "Copied from article pool",
      "importance": "high"
    }}
  ]
}}

The importance field must be one of: "high", "medium", "low".
Return ONLY valid JSON. No markdown fencing, no commentary outside the JSON.\
"""

# System prompt for grounding fallback (Canberra & Sports only)
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

# ---------------------------------------------------------------------------
# Topics — edit this list to change newsletter sections
# ---------------------------------------------------------------------------

TOPICS = [
    Topic(
        name="Climate Policy & Energy Transition",
        prompt=(
            "Select 3-5 of the most important stories about climate policy and "
            "energy transition. Prefer Australian climate and energy stories, but "
            "include major international developments (new targets, landmark rulings, "
            "significant investment or divestment, breakthrough technology). "
            "Exclude routine weather stories unless they're record-breaking.\n\n"
            "ARTICLE POOL:\n{articles}"
        ),
    ),
    Topic(
        name="AI & Technology",
        prompt=(
            "Select 3-5 of the most important stories about artificial intelligence "
            "and technology. Prioritise product launches with broad impact, major "
            "research breakthroughs, regulation and policy, significant funding or "
            "acquisitions, and security incidents. Skip routine corporate earnings "
            "and minor app updates.\n\n"
            "ARTICLE POOL:\n{articles}"
        ),
    ),
    Topic(
        name="Australian Politics & Public Sector",
        prompt=(
            "Select 3-5 of the most important Australian politics and public "
            "sector stories. Cover federal and state government decisions, policy "
            "announcements, parliamentary developments, and public service news. "
            "Prioritise decisions that affect everyday Australians. Skip minor "
            "political bickering or routine press releases.\n\n"
            "ARTICLE POOL:\n{articles}"
        ),
    ),
    Topic(
        name="Top Global Stories",
        prompt=(
            "Select 3-5 of the most important international news stories. "
            "Cover geopolitics, economics, conflict, diplomacy, and major world "
            "events. Exclude stories already covered under climate, AI, or "
            "Australian politics. Prefer stories with implications for the "
            "Asia-Pacific region or Australia.\n\n"
            "ARTICLE POOL:\n{articles}"
        ),
    ),
    Topic(
        name="Other Top Australian Stories",
        prompt=(
            "Select 3-5 significant Australian news stories that don't fit "
            "under climate/energy, AI/tech, or politics/public sector. "
            "Cover economics, business, health, culture, education, sport, "
            "or social issues. Prioritise stories with real impact or wide "
            "interest.\n\n"
            "ARTICLE POOL:\n{articles}"
        ),
    ),
    Topic(
        name="Canberra & ACT",
        prompt=(
            "Select 2-4 local Canberra and ACT news stories. Include ACT "
            "government decisions, local politics, community issues, "
            "infrastructure, housing, cost of living, and local events. "
            "Prioritise stories that directly affect Canberra residents.\n\n"
            "ARTICLE POOL:\n{articles}"
        ),
        use_grounding_fallback=True,
    ),
    Topic(
        name="Sports",
        prompt=(
            "Select up to 5 stories total about these three teams/sports: "
            "1) Middlesbrough FC (English Championship football), "
            "2) Canberra Raiders (NRL rugby league), "
            "3) Australia's men's cricket team. "
            "Include match results, upcoming fixtures, transfers, selections, "
            "or injury news. If a team hasn't played recently, it's fine to "
            "include fewer stories.\n\n"
            "ARTICLE POOL:\n{articles}"
        ),
        use_grounding_fallback=True,
    ),
]

# ---------------------------------------------------------------------------
# Email settings
# ---------------------------------------------------------------------------

EMAIL_SUBJECT_TEMPLATE = "First Light \u2014 {date}"
