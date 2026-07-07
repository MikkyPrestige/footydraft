"""Assembles the system + user prompts for draft generation."""
from curses import raw

import yaml
from datetime import datetime, timedelta
from sqlalchemy import desc
from core.database import SessionLocal
from core.models import Rule, Tweet, Draft
from core.ingestion.base import NewsItem
from datetime import datetime

# Load persona definitions once at module level
with open("config/personas.yaml", "r") as f:
    _PERSONAS = yaml.safe_load(f)

BASE_IDENTITY = _PERSONAS["base_identity"]
MODES = _PERSONAS["modes"]

# Map event tags to modes
TAG_TO_MODE = {}
for mode_name, mode_data in MODES.items():
    for trigger in mode_data["trigger"]:
        TAG_TO_MODE[trigger] = mode_name

def get_mode_for_tag(event_tag: str) -> str:
    """Return the persona mode name for a given event tag, defaulting to pundit."""
    return TAG_TO_MODE.get(event_tag, "pundit")

def build_prompt(item: NewsItem, event_tag: str, mode: str = None) -> tuple[str, str]:
    """
    Build system prompt and user prompt for a given news item and event tag.

    Args:
        item: The NewsItem to generate a tweet for.
        event_tag: The classified event type (e.g., LIVE_GOAL, TRANSFER).
        mode: Optionally force a specific persona mode. If None, derived from tag.

    Returns:
        (system_prompt, user_prompt) as strings.
    """
    if mode is None:
        mode = get_mode_for_tag(event_tag)

    # Base identity + mode-specific prompt
    mode_prompt = MODES[mode]["prompt"]
    system = BASE_IDENTITY.strip() + "\n\n" + mode_prompt.strip()
    # Add current date and hard rule to prevent hallucination
    today = datetime.utcnow().strftime("%d %B %Y")
    system += f"\n\nToday is {today}. Only use information present in the news item title or raw text. Do not mention players, managers, or events that are not explicitly mentioned in the item. Do not assume any current state of clubs or players based on your training data. The UEFA Champions League no longer drops eliminated teams into the Europa League."

    # Add active rules from database
    with SessionLocal() as session:
        active_rules = session.query(Rule).filter_by(active=True).all()
        if active_rules:
            rules_text = "\n".join([f"- {r.rule_text}" for r in active_rules])
            system += "\n\nStyle guidelines:\n" + rules_text

    # Fetch top few-shot examples for this content type
    content_type = "live" if event_tag.startswith("LIVE_") else "normal"
    with SessionLocal() as session:
        # Get top 3 tweets of similar content in last 30 days, ordered by likes
        cutoff = datetime.utcnow() - timedelta(days=30)
        top_tweets = (
            session.query(Tweet)
            .join(Draft, Tweet.draft_id == Draft.id)
            .filter(Tweet.posted_at >= cutoff)
            .filter(Draft.content_type == content_type)
            .order_by(desc(Tweet.likes))
            .limit(3)
            .all()
        )
        if top_tweets:
            examples = "\n".join([f"Example: {t.text}" for t in top_tweets])
            system += "\n\nFor reference, here are your best recent tweets in this category:\n" + examples

    # User prompt: simple instruction with the event
    raw = item.raw_text.strip() if item.raw_text else ""
    if raw:
        user = f"Latest event: {item.title}\n\nDetails:\n{raw}\n\nWrite a tweet."
    else:
        user = f"Latest event: {item.title}\n\nWrite a tweet."
    return system, user
