# First Light

A daily AI-powered news briefing delivered to your inbox before coffee.

First Light uses the Anthropic API with web search to find and summarise the day's top news, generates a mobile-friendly HTML email, and sends it via Gmail. It runs automatically as a GitHub Actions workflow.

## Topics

The default newsletter covers:

- **Climate Policy & Energy Transition** — Australian and international
- **AI & Technology** — product launches, research, regulation
- **Australian Politics & Public Sector** — federal/state government, policy
- **Top Global Stories** — geopolitics, economics, major world events
- **Other Top Australian Stories** — business, health, culture, education
- **Sports** — Middlesbrough FC, Canberra Raiders, Australia men's cricket

## Setup

### 1. Prerequisites

- An [Anthropic API key](https://console.anthropic.com/)
- A Gmail account with 2-Factor Authentication enabled

### 2. Create a Google App Password

Google App Passwords let apps sign in to your Gmail without using your main password.

1. Go to [myaccount.google.com](https://myaccount.google.com/)
2. Navigate to **Security** (left sidebar)
3. Under "How you sign in to Google", ensure **2-Step Verification** is turned on
4. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
5. Enter a name (e.g. "First Light") and click **Create**
6. Copy the 16-character password that appears — you'll need it in the next step
7. You won't be able to see this password again, so save it somewhere safe

### 3. Add GitHub Secrets

Go to your repository on GitHub, then **Settings > Secrets and variables > Actions > New repository secret**. Add these four secrets:

| Secret name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic API key (starts with `sk-ant-`) |
| `GMAIL_ADDRESS` | Your Gmail address (e.g. `you@gmail.com`) |
| `GMAIL_APP_PASSWORD` | The 16-character App Password from step 2 |
| `RECIPIENT_EMAIL` | Email address to receive the newsletter |

### 4. Push and test

Push the code to your repository, then trigger a test run:

1. Go to the **Actions** tab in your GitHub repository
2. Click **First Light Newsletter** in the left sidebar
3. Click **Run workflow** > **Run workflow**
4. Wait for the run to complete (usually 2-3 minutes)
5. Check your inbox

## Customising Topics

Edit `src/config.py` to change what the newsletter covers. Each topic is a simple entry in the `TOPICS` list:

```python
Topic(
    name="Section Heading in Email",
    prompt="Instructions for what Claude should search and summarise.",
    max_uses=4,  # max web searches for this topic (2-5)
),
```

To add a topic, copy an existing entry and modify it. To remove one, delete or comment it out.

## Adjusting the Schedule

The schedule is set in `.github/workflows/newsletter.yml`:

```yaml
schedule:
  - cron: '30 19 * * *'
```

This cron expression is in UTC. The default (`30 19 * * *`) targets **6:30am AEDT** (Canberra daylight saving time). During AEST (April–October), the email arrives at 5:30am instead.

To change the time, update the cron expression. Some examples:
- `0 20 * * *` — 6:00am AEST / 7:00am AEDT
- `0 21 * * *` — 7:00am AEST / 8:00am AEDT
- `30 20 * * *` — 6:30am AEST / 7:30am AEDT

Use [crontab.guru](https://crontab.guru/) to build cron expressions.

## Local Development

1. Copy `.env.example` to `.env` and fill in your values
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Source your environment and run:
   ```
   export $(grep -v '^#' .env | xargs)
   python -m src.main
   ```

## Cost

Approximately **$12–15 per month** for daily runs:
- ~25 web searches/day at $0.01/search = ~$0.25/day
- ~$0.10–0.20/day in API token costs
- Gmail SMTP is free

## Architecture

```
src/
├── config.py          # Topics, model settings, prompts (edit this)
├── news_fetcher.py    # Anthropic API calls + response parsing
├── email_builder.py   # HTML + plain-text email assembly
├── email_sender.py    # Gmail SMTP sending
└── main.py            # Orchestrator: fetch → build → send
```

The workflow calls `python -m src.main`, which:
1. Validates environment variables
2. Makes one API call per topic (with web search enabled)
3. Parses the JSON response and extracts stories with source links
4. Assembles a mobile-friendly HTML email with a plain-text fallback
5. Sends via Gmail SMTP
