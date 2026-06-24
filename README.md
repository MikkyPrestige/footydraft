# ⚽ Football X Agent

An AI‑powered assistant that helps you run a high‑quality, on‑trend football Twitter (X) account.  
It continuously monitors **free** news sources, generates context‑aware tweet drafts using a large language model, and delivers them to you via a Telegram bot for manual review, copying, and optional Xquik posting.
Over time, it learns from your engagement metrics to refine its writing style - all while keeping **you** in full control.

---

## ✨ Features

- **Real‑time news ingestion** (RSS, Reddit, Google News, API‑Football) - 100% free
- **Hybrid tweet drafting** with three personas (pundit, fan, analyst)  
- **Three variants per normal event**, one per live match event  
- **Telegram bot** for reviewing, copying, and tracking drafts  
- **Manual feedback loop** - enter tweet engagement metrics without the X API
- **Optional Xquik posting** - publish approved drafts only when `XQUIK_POSTING_ENABLED=1`
- **Weekly analytics** that suggest style improvements based on your best‑performing tweets  
- **Deduplication & age filters** to avoid stale or repeated content  
- **Deployable 24/7** on Fly.io (or any Docker‑compatible platform) - costs < $2/month

---

## 🧠 How It Works

1. **News Fetchers** pull headlines from BBC, Sky Sports, ESPN, The Guardian, Daily Mail, Reddit, Google News, and live match data from API‑Football.  
2. **Event Classifier** tags each story (goal, transfer, stats, debate, meme, etc.) using keyword rules.  
3. **Deduplication Engine** ensures the same story doesn’t generate repeated drafts within 24 hours.  
4. **Prompt Builder** combines your account’s persona, the selected mode (pundit/fan/analyst), active style rules, and your top‑performing tweets as few‑shot examples.  
5. **LLM Client** (Groq, free tier) generates tweet drafts.  
6. **Telegram Bot** shows pending drafts in a queue with inline “Copy” buttons, optional `/postx` publishing, and instant live‑event drafts.
7. **Analytics Engine** runs weekly, identifies patterns in your engagement data, and suggests natural‑language rules you can approve or reject.

---

## 🏗 Architecture

```
football-x-agent/
├── config/          # Persona definitions, settings
├── core/            # Engine (UI‑agnostic)
│   ├── ingestion/   # News fetchers (RSS, Reddit, Google News, API‑Football)
│   ├── classification/  # Event tagger, deduplication
│   ├── generation/  # Prompt builder, LLM client, queue manager
│   ├── tracking/    # (future) automatic tweet matching
│   └── analytics/   # Weekly performance analysis
├── bot/             # Telegram bot interface
├── data/            # SQLite database (auto‑created)
├── tests/           # Unit & integration tests
├── Dockerfile       # Containerised deployment
├── fly.toml         # Fly.io configuration
└── start.sh         # Startup script (runs both scheduler & bot)
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
- `/start` – welcome message
- `/queue` – view pending normal drafts
- `/posted <draft_id>` – mark a draft as posted
- `/postx <draft_id> [variant]` – post an approved draft with Xquik
- `/metrics <tweet_ref> <likes> <retweets> <replies> <impressions>` – enter engagement
- `/stats` – top & bottom tweets
- `/rules` – manage style rules
- `/addrule <text>` – add a manual rule
- `/source_status` – health of news sources
- `/backup` – download a copy of the database

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
4. Set secrets (replace with your values):
   ```bash
   flyctl secrets set OPENAI_API_KEY="sk-..." TELEGRAM_BOT_TOKEN="123:abc" ... -a football-x-agent
   ```
5. Deploy:
   ```bash
   flyctl deploy -a football-x-agent
   ```
6. Check logs: `flyctl logs -a football-x-agent`

Your bot will now run 24/7 without needing your computer.

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

---

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

- [ ] Web dashboard (Streamlit)
- [ ] Optional scheduled auto‑posting with kill‑switch
- [ ] More news sources (Livescore, OneFootball)
- [ ] Multi‑language support

---

## 👐 Contributing

Contributions are welcome! This is a personal project, but if you have ideas for improvements or new fetchers, feel free to open a PR or issue. Please keep the core UI‑agnostic principle in mind.

---
