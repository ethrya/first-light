# First Light

A daily AI-powered news briefing delivered to your inbox each morning.

First Light pulls articles from RSS feeds, uses Gemini to pre-screen and rank them by newsworthiness, then uses Claude (Anthropic) to write a curated newsletter with tiered stories, a short editorial intro, and source links. It runs automatically via GitHub Actions and sends via Gmail.

## How it works

```
RSS feeds (900+ articles/day)
    │
    ▼
Gemini pre-screen — ranks and filters each topic down to ~6-7 articles
    │
    ▼
Claude Sonnet — reads the shortlist, writes the newsletter as structured JSON
    │
    ▼
Email builder — assembles HTML + plain-text email
    │
    ▼
Gmail SMTP — sends to your inbox
```

**Cost:** ~$0.10/day ($3/month) — mostly Claude Sonnet for writing. Gemini pre-screen adds ~$0.005/day.

## Topics covered

- **Australia** — top national stories: politics, economy, society
- **Australian Politics** — federal parliament, policy, public service
- **Canberra & ACT** — local government, community, infrastructure
- **Global** — geopolitics, economics, major world events
- **Climate & Energy** — Australian and international energy transition
- **AI & Tech** — product launches, research, regulation
- **Sports** — Australian sport, customisable to your interests

Each topic is fully customisable — see [Customising Topics](#customising-topics) below.

## Setup

### 1. Get an Anthropic API key

Claude does the editorial writing. You need an Anthropic API key.

1. Go to [console.anthropic.com](https://console.anthropic.com/)
2. Sign up or log in
3. Go to **API Keys** and create a new key
4. Copy the key — it starts with `sk-ant-`

### 2. Get a Google AI API key

Gemini handles pre-screening articles and grounded search for some topics.

1. Go to [aistudio.google.com](https://aistudio.google.com/)
2. Click **Get API key** → **Create API key**
3. Copy the key — it starts with `AIza`

### 3. Create a Gmail App Password

App Passwords let the script send email via Gmail without exposing your main password.

1. Make sure [2-Step Verification](https://myaccount.google.com/security) is enabled on your Google account
2. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Enter a name (e.g. "First Light") and click **Create**
4. Copy the 16-character password — you won't be able to see it again

### 4. Fork and add GitHub Secrets

Fork this repo, then go to **Settings > Secrets and variables > Actions > New repository secret** and add:

| Secret name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic API key (`sk-ant-...`) |
| `GOOGLE_API_KEY` | Your Google AI Studio API key (`AIza...`) |
| `GMAIL_ADDRESS` | The Gmail address to send from |
| `GMAIL_APP_PASSWORD` | The 16-character App Password from step 3 |
| `RECIPIENT_EMAIL` | Email address to receive the newsletter |

### 5. Test it

1. Go to the **Actions** tab in your GitHub repository
2. Click **First Light Newsletter** in the left sidebar
3. Click **Run workflow** → **Run workflow**
4. Wait ~5 minutes, then check your inbox

## Customising Topics

Edit `src/config.py`. Each topic is a `Topic` entry in the `TOPICS` list:

```python
Topic(
    name="AI & Tech",           # section heading in the email
    display_name="AI & Tech",   # optional display override
    prompt="...",               # instructions for the editorial AI
    max_stories=4,              # max stories to include
),
```

To add a topic, copy an existing entry and modify it. To remove one, delete or comment it out.

Some topics use `use_grounding_fallback=True` — this triggers a Gemini Google Search to supplement thin RSS coverage (used for Canberra local news and Sports by default).

## Adjusting the Schedule

The schedule is set in `.github/workflows/newsletter.yml`:

```yaml
schedule:
  - cron: '30 20 * * *'
```

Cron times are in UTC. The default (`30 20 * * *`) targets **6:30am AEST** (UTC+10). During daylight saving (AEDT, UTC+11) the email arrives at 7:30am. Note that GitHub Actions can queue for up to 30 minutes during busy periods.

Some useful times for Australian Eastern time:

| Cron (UTC) | AEST (winter) | AEDT (summer) |
|---|---|---|
| `0 19 * * *` | 5:00am | 6:00am |
| `30 19 * * *` | 5:30am | 6:30am |
| `0 20 * * *` | 6:00am | 7:00am |
| `30 20 * * *` | 6:30am | 7:30am |

Use [crontab.guru](https://crontab.guru/) to build cron expressions.

## Switching the editorial engine

By default Claude Sonnet writes the newsletter. You can test Gemini instead via a manual workflow run — go to **Actions → First Light Newsletter → Run workflow** and set `editorial_engine` to `gemini`.

Gemini writing costs ~$0.015/run vs ~$0.10 for Claude Sonnet, but produces noticeably lower quality output (flatter writing, occasional formatting issues).

## Local Development

1. Copy `.env.example` to `.env` and fill in your keys
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Run:
   ```
   export $(grep -v '^#' .env | xargs)
   python -m src.main
   ```

## Architecture

```
src/
├── config.py          # Topics, prompts, model settings — edit this
├── feeds.py           # RSS feed URLs per topic
├── rss_fetcher.py     # Fetches and parses RSS feeds
├── news_fetcher.py    # Pre-screen (Gemini) + editorial (Claude/Gemini)
├── watch_today.py     # "What to watch today" section via Gemini grounding
├── weather.py         # Canberra weather via Open-Meteo
├── dedup.py           # Cross-feed article deduplication
├── email_builder.py   # HTML + plain-text email assembly
├── email_sender.py    # Gmail SMTP sending
└── main.py            # Orchestrator
```
