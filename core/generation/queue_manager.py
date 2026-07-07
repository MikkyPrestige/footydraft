"""Queue manager: creates Draft records for news items, respecting caps."""
from datetime import datetime, timedelta
from core.database import SessionLocal
from core.models import Draft
from core.ingestion.base import NewsItem
from core.classification.event_tagger import classify_item
from core.classification.dedup import is_duplicate
from core.generation.prompt_builder import build_prompt, get_mode_for_tag
from core.generation.llm_client import generate_tweet
from config.settings import NORMAL_DAILY_CAP

async def process_item(item: NewsItem) -> Draft | None:
    """
    Classify, deduplicate, generate draft(s) for a single NewsItem.
    Returns the created Draft or None if skipped.
    """
    event_tag = classify_item(item)
    if is_duplicate(item, event_tag):
        print(f"Duplicate skipped: {item.title}")
        return None

    mode = get_mode_for_tag(event_tag)
    if event_tag.startswith("LIVE_"):
        content_type = "live"
    elif event_tag == "STAT_INSIGHT":
        content_type = "stats"
    else:
        content_type = "normal"

    # Check daily cap for normal drafts
    if content_type == "normal":
        with SessionLocal() as session:
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            count = session.query(Draft).filter(
                Draft.content_type == "normal",
                Draft.status == "posted",
                Draft.created_at >= today_start
            ).count()
            if count >= NORMAL_DAILY_CAP:
                print(f"Daily normal cap ({NORMAL_DAILY_CAP}) reached. Skipping {item.title}")
                return None

    # Build prompt and generate variants
    system_prompt, user_prompt = build_prompt(item, event_tag, mode)
    n_variants = 1 if content_type == "live" else 3
    try:
        variants = generate_tweet(system_prompt, user_prompt, n=n_variants)
    except Exception as e:
        print(f"LLM failed for {item.title}: {e}")
        return None

    draft_status = "pending_live" if content_type == "live" else "pending"
    # For live events, select variant 0 (the only one) implicitly
    selected = 0 if content_type == "live" else None

    draft = Draft(
        event_hash=item.title,  # temporary; will be replaced by dedup hash
        content_type=content_type,
        persona=mode,
        status=draft_status,
        text_variants=variants,
        selected_variant=selected,
    )
    with SessionLocal() as session:
        session.add(draft)
        session.commit()
        session.refresh(draft)
    return draft
