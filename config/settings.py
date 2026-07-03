import os
from dotenv import load_dotenv

load_dotenv()

# API keys and tokens
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")          # set to your Groq key
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")              # keep as backup
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")
THESPORTSDB_API_KEY = os.getenv("THESPORTSDB_API_KEY", "3")
XQUIK_API_KEY = os.getenv("XQUIK_API_KEY")
XQUIK_API_BASE_URL = os.getenv("XQUIK_API_BASE_URL", "https://xquik.com").rstrip("/")
XQUIK_POSTING_ENABLED = os.getenv("XQUIK_POSTING_ENABLED", "0").lower() in {"1", "true", "yes", "on"}

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/agent.db")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

# Caps and limits
NORMAL_DAILY_CAP = 5          # max normal tweets posted per day
LIVE_MATCH_HOURLY_CAP = 10    # max live tweets per match hour

# Intervals (in seconds or minutes)
NEWS_FETCH_INTERVAL_MINUTES = int(os.getenv("NEWS_FETCH_INTERVAL_MINUTES", 2))
TWEET_POLL_INTERVAL_SECONDS = int(os.getenv("TWEET_POLL_INTERVAL_SECONDS", 300))
MAX_ITEM_AGE_HOURS = int(os.getenv('MAX_ITEM_AGE_HOURS', '12'))


# Dropbox backup
DROPBOX_APP_KEY = os.getenv("DROPBOX_APP_KEY")
DROPBOX_APP_SECRET = os.getenv("DROPBOX_APP_SECRET")
DROPBOX_REFRESH_TOKEN = os.getenv("DROPBOX_REFRESH_TOKEN")
SENTRY_DSN = os.getenv('SENTRY_DSN')

# Fly.io runtime variables (automatically set by Fly.io)
FLY_APP_NAME = os.getenv("FLY_APP_NAME")
FLY_MACHINE_ID = os.getenv("FLY_MACHINE_ID")
FLY_API_TOKEN = os.getenv("FLY_API_TOKEN")
