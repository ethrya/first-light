# First Light

A daily AI-powered news briefing delivered to your inbox before coffee.

First Light uses the Gemini API with Google Search grounding to find and summarise the day's top news, generates a mobile-friendly HTML email, and sends it via Gmail. It runs automatically as a GitHub Actions workflow.

## Topics

- **Climate Policy & Energy Transition** — Australian and international
- **AI & Technology** — product launches, research, regulation
- **Australian Politics & Public Sector** — federal/state government, policy
- **Top Global Stories** — geopolitics, economics, major world events
- **Other Top Australian Stories** — business, health, culture, education
- **Canberra & ACT** — local government, community, infrastructure
- **Sports** — Middlesbrough FC, Canberra Raiders, Australia men's cricket

## Setup

### 1. Get a Google Cloud API key

1. Go to [console.cloud.google.com](https://console.cloud.google.com/)
2. Select or create a project
3. Enable the **Generative Language API** (APIs & Services → Enable APIs → search "Generative Language")
4. Go to **APIs & Services → Credentials → Create Credentials → API key**
5. Copy the key — you'll need it below

At current usage (~24 searches/day, well under the 5,000 free grounding queries/month), the cost is roughly **$1/month** in token charges.

### 2. Create a Gmail App Password

Gmail App Passwords let apps sign in to your Gmail without using your main password.

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
| `GOOGLE_API_KEY` | Your Google AI Studio API key (starts with `AIza`) |
| `GMAIL_ADDRESS` | Your Gmail address (e.g. `you@gmail.com`) |
| `GMAIL_APP_PASSWORD` | The 16-character App Password from step 2 |
| `RECIPIENT_EMAIL` | Email address to receive the newsletter |

### 4. Push and test

Push the code to your repository, then trigger a test run:

1. Go to the **Actions** tab in your GitHub repository
2. Click **First Light Newsletter** in the left sidebar
3. Click **Run workflow** > **Run workflow**
4. Wait for the run to complete (usually 3-5 minutes)
5. Check your inbox

## Customising Topics

Edit `src/config.py` to change what the newsletter covers. Each topic is a simple entry in the `TOPICS` list:

```python
Topic(
    name="Section Heading in Email",
    prompt="Instructions for what Gemini should search and summarise. Be specific about search terms.",
    max_uses=4,  # informational only; Gemini searches automatically as needed
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

Approximately **$1/month** for daily runs:
- Google Search Grounding: free up to 5,000 queries/month (we use ~720/month)
- Gemini 3 Flash token costs: ~$0.036/day in input + output tokens
- Gmail SMTP is free

## Architecture

```
src/
├── config.py          # Topics, model settings, prompts (edit this)
├── news_fetcher.py    # Gemini API + Google Search grounding
├── email_builder.py   # HTML + plain-text email assembly
├── email_sender.py    # Gmail SMTP sending
└── main.py            # Orchestrator: fetch → build → send
```

The workflow calls `python -m src.main`, which:
1. Validates environment variables
2. Makes one Gemini API call per topic with Google Search grounding
3. Parses the JSON response and extracts stories with source links
4. Generates a short conversational intro paragraph from the top headlines
5. Assembles a mobile-friendly HTML email with a plain-text fallback
6. Sends via Gmail SMTP
