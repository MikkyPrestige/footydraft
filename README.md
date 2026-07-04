# ⚽ Football X Agent

An AI powered assistant that helps you run a high‑quality, on‑trend football Twitter (X) account.
It continuously monitors **free** news sources, generates context‑aware tweet drafts using a large language model, and delivers them to you via a Telegram bot for manual review, copying, and optional Xquik posting.
Over time, it learns from your engagement metrics to refine its writing style - all while keeping **you** in full control.

---

## ✨ Features

- **Real‑time news ingestion** (RSS, Reddit, Google News, API‑Football) - 100% free
- **Interactive Streamlit Dashboard** – view drafts, performance analytics, source health, rules, and backups in one place
- **Hybrid tweet drafting** with three personas (pundit, fan, analyst)
- **Three variants per normal event**, one per live match event
- **Telegram bot** for reviewing, copying, and tracking drafts
- **Manual feedback loop** - enter tweet engagement metrics without the X API
- **Optional Xquik posting** - publish approved drafts only when `XQUIK_POSTING_ENABLED=1`
- **Automatic database backups** – compressed backup on every boot and nightly at 3 AM UTC (Dropbox primary, Telegram secondary)
- **Real‑time error tracking** – Sentry integration to monitor crashes and bugs
- **Built‑in uptime monitor** – `/uptime` command shows how long the bot has been running (WAT)
- **Gated database restore** – `/restore` command with one‑time code, backup file picker, and automatic staging
- **Safe remote restart** – `/restart` with two‑step confirmation, no computer needed
- **Weekly analytics** that suggest style improvements based on your best‑performing tweets
- **Deduplication & age filters** to avoid stale or repeated content
- **Deployable 24/7** on Fly.io (or any Docker‑compatible platform)

---

## 🧠 How It Works

1. **News Fetchers** pull headlines from BBC, Sky Sports, ESPN, The Guardian, Daily Mail, Reddit, Google News, and live match data from API‑Football.
2. **Event Classifier** tags each story (goal, transfer, stats, debate, meme, etc.) using keyword rules.
3. **Deduplication Engine** ensures the same story doesn’t generate repeated drafts within 24 hours.
4. **Prompt Builder** combines your account’s persona, the selected mode (pundit/fan/analyst), active style rules, and your top‑performing tweets as few‑shot examples.
5. **LLM Client** (Groq, free tier) generates tweet drafts.
6. **Telegram Bot** shows pending drafts in a queue with inline “Copy” buttons, optional `/postx` publishing, and instant live‑event drafts.
7. **Analytics Engine** runs weekly, identifies patterns in your engagement data, and suggests natural‑language rules you can approve or reject.
8. **Backup Engine** – automatically creates a gzipped database backup on every machine restart and daily at 3 AM UTC, uploading to Dropbox (primary) and Telegram (secondary).
9. **Monitoring** – the `/uptime` command shows the bot’s start time and elapsed uptime; Sentry integration tracks errors in real time.
10. **Recovery** – the `/restore` command uses a gated one‑time code to list the last 5 backups from Dropbox, then stages the selected backup; a `/restart` reboot applies it automatically.

---

## 🏗 Architecture

```
football-x-agent/
├── config/
│   ├── settings.py          # Environment variables & constants
│   └── personas.yaml        # Persona definitions (pundit, fan, analyst)
├── core/                    # Engine (UI‑agnostic)
│   ├── ingestion/           # News fetchers
│   │   ├── base.py          # Abstract BaseFetcher + NewsItem
│   │   ├── rss_fetcher.py   # BBC, Sky, ESPN, Guardian, etc.
│   │   ├── reddit_fetcher.py
│   │   ├── google_news_fetcher.py
│   │   ├── api_football_fetcher.py
│   │   ├── espn_fetcher.py  # ESPN hidden API (CL, Europa, cups)
│   │   └── monitor.py       # Source health monitoring
│   ├── classification/
│   │   ├── event_tagger.py  # Keyword‑based tagger
│   │   └── dedup.py         # Content‑hash deduplication
│   ├── generation/
│   │   ├── prompt_builder.py
│   │   ├── llm_client.py    # Groq (primary), DeepSeek (fallback)
│   │   └── queue_manager.py # Draft creation & daily caps
│   ├── publishing/          # Optional Xquik posting
│   │   ├── __init__.py
│   │   └── xquik.py
│   ├── analytics/
│   │   └── engine.py        # Weekly rule suggestions
│   ├── backup.py            # Dropbox & Telegram backup (gzipped)
│   ├── database.py          # SQLAlchemy init & session
│   ├── models.py            # ORM models (Draft, Tweet, Rule, etc.)
│   └── scheduler.py         # Main loop
├── bot/
│   ├── handlers.py          # All command handlers
│   ├── keyboard.py          # Inline keyboards (Copy, pagination)
│   └── main.py              # Bot entry point + live‑draft push
├── dashboard/               # Streamlit dashboard
│   ├── app.py               # Main dashboard entry point
│   ├── ui_components.py     # Shared UI (CSS, sidebar, navigation)
│   ├── utils.py             # Shared utilities (Dropbox, database helpers)
│   ├── requirements.txt     # Dashboard dependencies
│   ├── Dockerfile.dashboard # Dockerfile for dashboard service
│   ├── static/              # Static assets (favicon, etc.)
│   └── pages/               # Dashboard pages
│       ├── Backup_Browser.py
│       ├── Database_Stats.py
│       ├── Drafts.py
│       ├── Live_Check.py
│       ├── Performance.py
│       ├── Rule_Manager.py
│       └── Source_Health.py
├── data/                    # SQLite database (auto‑created)
├── tests/                   # Unit & integration tests
├── .env.example             # Environment template
├── Dockerfile               # Containerised deployment
├── fly.toml                 # Fly.io configuration
├── requirements.txt
├── start.sh                 # Startup script (scheduler + bot)
└── README.md
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- A **Groq** API key (free tier)
- A **Telegram bot token** (from [@BotFather](https://t.me/BotFather))
- (Optional) API‑Football key for live match data (free tier)

### 1. Clone & set up environment
```bash
git clone https://github.com/MikkyPrestige/football-x-agent.git
cd football-x-agent
python -m venv venv
source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env
# Now edit .env with your real API keys
```

### 2. Initialise the database
```bash
python -c "from core.database import init_db; init_db()"
```

### 3. Run the scheduler & bot locally
**Terminal 1 – Core scheduler** (fetches news, generates drafts):
```bash
python -m core.scheduler
```

**Terminal 2 – Telegram bot**:
```bash
python -m bot.main
```

### 4. Open Telegram & try commands
- `/start` – welcome message with full command list
- `/queue` – view pending drafts (all, normal, or live) with Copy buttons & pagination
- `/queue normal` – only normal pending drafts
- `/queue live` – only live-match drafts
- `/drafts` – browse all drafts (`all`, `pending`, `held`, `posted`) with pagination
- `/hold <draft_id>` – quarantine a pending draft
- `/release <draft_id>` – return a held draft to the queue
- `/posted <draft_id>` – mark a draft as manually posted & link a tweet
- `/postx <draft_id> [variant]` – post an approved draft via Xquik (requires `XQUIK_POSTING_ENABLED=1`)
- `/metrics <tweet_ref> <likes> <retweets> <replies> <impressions>` – enter engagement
- `/stats` – top & bottom tweets by likes (default), impressions, or list all posted tweets
- `/tweets` – list all posted tweets with refs
- `/impressions` – top & bottom tweets by impressions
- `/rules` – manage style rules (accept/reject auto‑suggestions)
- `/addrule <text>` – add a manual style rule
- `/source_status` – health of news sources
- `/livecheck` – force check for live matches
- `/clearqueue` – delete all pending drafts (or only `normal` / `live`)
- `/uptime` – bot uptime and start time (WAT)
- `/restore` – gated database restore from Dropbox backups
- `/restart` – Restart the bot (two-step confirmation)


### 5. (Optional) Run the Streamlit Dashboard

```bash
# Install dashboard dependencies
pip install -r dashboard/requirements.txt

# Run the dashboard
streamlit run dashboard/app.py
```
> The dashboard will be available at http://localhost:8501


### 6. (Optional) Run both bot and dashboard with Docker Compose
**Start both services**
```bash
docker compose up -d
```

**Start only the dashboard**
```bash
docker compose up -d dashboard
```

**Start only the bot**
```bash
docker compose up -d bot
```

> The dashboard will be available at http://localhost:8501

---

## ☁️ Deploying to Fly.io (24/7)

The project includes a `Dockerfile` and `fly.toml` for one‑click deployment to [Fly.io](https://fly.io).
It runs both the scheduler and the Telegram bot in a single small VM (~$1.94/month).

1. Install the **Fly CLI**: `curl -L https://fly.io/install.sh | sh`
2. Log in: `flyctl auth login`
3. Create the app & volume (run inside the project folder):
   ```bash
   flyctl apps create football-x-agent --yes
   flyctl volumes create agent_data --region iad --size 1 -a football-x-agent
   ```
4. Set secrets (replace with your values): `flyctl secrets set OPENAI_API_KEY="sk-..." TELEGRAM_BOT_TOKEN="123:abc" ... -a football-x-agent`
5. Deploy: `flyctl deploy -a football-x-agent`
6. Check logs: `flyctl logs -a football-x-agent`

> Your bot will now run 24/7 without needing your computer.

---

## 📊 Deploying the Dashboard to Streamlit Cloud (24/7)

The dashboard can be deployed to [Streamlit Cloud](https://streamlit.io/cloud) for 24/7 access.

1. Push your code to GitHub.
2. Go to [Streamlit Cloud](https://share.streamlit.io/) and sign in with GitHub.
3. Click **"New app"** and select your repository.
4. Set the main file path to: `dashboard/app.py`
5. In **Settings** → **Secrets**, add the following environment variables:

```toml
DROPBOX_APP_KEY = "your_key"
DROPBOX_APP_SECRET = "your_secret"
DROPBOX_REFRESH_TOKEN = "your_token"
TELEGRAM_BOT_TOKEN = "your_token"
ADMIN_CHAT_ID = "your_chat_id"

# Required for Xquik toggle (via Fly.io CLI only)
XQUIK_POSTING_ENABLED = "1"

# Required if using Xquik toggle (optional)
FLY_API_TOKEN = "your_token"
FLY_APP_NAME = "football-x-agent"
FLY_MACHINE_ID = "your_machine_id"
```

6. Click Deploy.

> The dashboard will be available at https://your-app-name.streamlit.app

---

## ⚙️ Configuration

All important settings are in `config/settings.py` and can be overridden with environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | – | API key (Groq or any OpenAI‑compatible provider) |
| `TELEGRAM_BOT_TOKEN` | – | Telegram bot token |
| `GROQ_API_KEY` | – | Groq API key (fallback) |
| `API_FOOTBALL_KEY` | – | API‑Football key (optional) |
| `DATABASE_URL` | `sqlite:///data/agent.db` | DB connection string |
| `XQUIK_POSTING_ENABLED` | `0` | Set to `1` to enable `/postx` publishing |
| `XQUIK_API_KEY` | – | Xquik API key used by `/postx` |
| `XQUIK_API_BASE_URL` | `https://xquik.com` | Override for custom Xquik deployments |
| `NORMAL_DAILY_CAP` | 5 | Max normal tweets posted per day |
| `LIVE_MATCH_HOURLY_CAP` | 10 | Max live tweets per match hour |
| `MAX_ITEM_AGE_HOURS` | 12 | Discard news older than this |
| `DROPBOX_APP_KEY` | – | Dropbox app key for automatic backups |
| `DROPBOX_APP_SECRET` | – | Dropbox app secret |
| `DROPBOX_REFRESH_TOKEN` | – | Dropbox refresh token (never expires) |
| `SENTRY_DSN` | – | Sentry DSN for error tracking |
| `FLY_API_TOKEN` | – | Fly.io org token (required for `/restart`) |
| `STREAMLIT_SERVER_PORT` | `8501` | Port for Streamlit dashboard |
| `STREAMLIT_SERVER_ADDRESS` | `0.0.0.0` | Address for Streamlit dashboard |

---

## 🔐 Xquik Posting Control

Xquik posting allows the bot to automatically post tweets to X (Twitter). This is controlled via Fly.io environment variables.

**Enable Xquik**
```bash
flyctl secrets set XQUIK_POSTING_ENABLED=1 -a football-x-agent
flyctl machines restart <machine_id> -a football-x-agent
```

**Disable Xquik**
```bash
flyctl secrets set XQUIK_POSTING_ENABLED=0 -a football-x-agent
flyctl machines restart <machine_id> -a football-x-agent
```

**Get machine ID**
```bash
flyctl machines list -a football-x-agent
```

> The `/postx` command in the Telegram bot will only work when `XQUIK_POSTING_ENABLED=1`

> [!NOTE] The Xquik toggle has been removed from the Streamlit dashboard due to persistence issues on Streamlit Cloud. The backend functionality remains fully available via the Fly.io CLI.


## 🧪 Testing

```bash
# Run individual test scripts
python -m tests.test_rss_fetcher
python -m tests.test_llm_client
python -m tests.test_queue_manager
# … and more under tests/
```

---

## 🗺 Roadmap / Future

- [ ] Optional scheduled auto‑posting with kill‑switch
- [ ] More news sources (Livescore, OneFootball)
- [ ] Multi‑language support

---

## 👐 Contributing

Contributions are welcome! This is a personal project, but if you have ideas for improvements or new fetchers, feel free to open a PR or issue. Please keep the core UI‑agnostic principle in mind.

---
