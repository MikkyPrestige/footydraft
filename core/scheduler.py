"""Main scheduler loop: ingestion → classification → dedup → draft generation."""
import asyncio
import time
import schedule
import random
from datetime import datetime, timedelta
from core.ingestion.rss_fetcher import RSSFetcher, FAST_FEEDS
from core.ingestion.reddit_fetcher import RedditFetcher
from core.ingestion.google_news_fetcher import GoogleNewsFetcher
from core.ingestion.api_football_fetcher import APIFootballFetcher
from core.ingestion.espn_fetcher import ESPNFetcher
from core.generation.queue_manager import process_item
from core.analytics.engine import run_weekly_analytics
from core.backup import daily_backup as daily_backup_job
import sentry_sdk
from config.settings import SENTRY_DSN
sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=1.0)

MAX_ITEMS_PER_SOURCE = 5
MAX_LLM_CALLS_PER_CYCLE = 6
MAX_AGE_HOURS = 12  # hours

RELEVANCE_KEYWORDS = {
    # original keywords
    "goal", "transfer", "sign", "deal", "rumour", "injury", "manager",
    "sack", "appoint", "champion", "relegation", "promotion",
    "var", "red card", "yellow card", "hattrick", "brace", "derby",
    "el clasico", "classique", "rival", "record", "stats",
    "premier league", "la liga", "serie a", "bundesliga", "ligue 1",
    "champions league", "europa league", "fa cup", "copa del rey",
    "world cup", "euro", "copa america", "afcon",
    # live match indicators (so status lines pass)
    "status", "vs", "1h", "2h", "ht", "ft", "elapsed",
    "minute", "half-time", "full-time", "kick-off",
    "substitution", "subbed",
    # expanded stats terms
    "xG", "xA", "progressive", "field tilt", "PPDA", "shot map",
    "heat map", "big chances", "possession", "pass completion",
    "tackles", "interceptions", "clearances", "duels", "assists",
    "saves", "clean sheet", "distance covered",
    # expanded transfer terms
    "here we go", "medical", "verbal agreement", "triggered", "activates",
    # expanded debate/meme terms
    "overrated", "underrated", "bottle", "cooking", "generational"
}

def is_relevant(item) -> bool:
    # check title first
    if any(kw in item.title.lower() for kw in RELEVANCE_KEYWORDS):
        return True
    # then check raw_text for stat or live indicators
    if item.raw_text:
        return any(kw in item.raw_text.lower() for kw in RELEVANCE_KEYWORDS)
    return False

async def fetch_fast_feeds():
    """Lightweight fetch of fast‑updating RSS feeds only. Called every 10 min."""
    fetcher = RSSFetcher(feeds=FAST_FEEDS, max_entries=100)
    print("⚡ Fast feed cycle starting...")
    items = await fetcher.fetch()
    print(f"  Fast feeds: got {len(items)} items")

    # Apply same age and relevance filters as the main cycle
    age_cutoff = datetime.utcnow() - timedelta(hours=MAX_AGE_HOURS)
    fresh = [it for it in items if it.published and it.published > age_cutoff]
    relevant = [it for it in fresh if is_relevant(it)]
    print(f"  Fast feeds: {len(relevant)} relevant fresh items")

    # Process up to 3 items per fast cycle to keep LLM calls low
    llm_calls = 0
    to_process = relevant[:3]
    for item in to_process:
        if llm_calls >= MAX_LLM_CALLS_PER_CYCLE:
            break
        await process_item(item)
        llm_calls += 3

async def fetch_all_and_process():
    fetchers = [
        ("RSS", RSSFetcher(max_entries=100)),
        ("Reddit", RedditFetcher(max_entries=100)),
        ("Google News", GoogleNewsFetcher(max_entries=100)),
        ("Google Stats", GoogleNewsFetcher(search_query="football statistics OR xG OR expected goals OR progressive passes OR shot map OR heat map OR big chances OR passing accuracy OR tackles OR interceptions", max_entries=100)),
        ("API-Football", APIFootballFetcher(max_entries=100)),
        ("ESPN", ESPNFetcher(max_entries=100)),
    ]
    llm_calls = 0
    now = datetime.utcnow()
    age_cutoff = now - timedelta(hours=MAX_AGE_HOURS)
    for name, fetcher in fetchers:
        if llm_calls >= MAX_LLM_CALLS_PER_CYCLE:
            print("  ⚠️ Reached cycle LLM call limit. Skipping remaining fetchers.")
            break
        print(f"Fetching {name}...")
        items = await fetcher.fetch()
        print(f"  {name}: got {len(items)} items")
        # 1. Remove items older than MAX_AGE_HOURS
        fresh_items = [item for item in items if item.published and item.published > age_cutoff]
        print(f"  {name}: {len(fresh_items)} fresh items (within {MAX_AGE_HOURS}h)")
        # 2. Apply relevance filter
        relevant = [item for item in fresh_items if is_relevant(item)]
        print(f"  {name}: {len(relevant)} relevant items")
        if not relevant:
            continue
        # 3. Shuffle and take up to MAX_ITEMS_PER_SOURCE
        sample_size = min(MAX_ITEMS_PER_SOURCE, len(relevant))
        to_process = random.sample(relevant, sample_size)
        print(f"  {name}: processing {len(to_process)} randomly selected items")
        for item in to_process:
            if llm_calls >= MAX_LLM_CALLS_PER_CYCLE:
                print("  ⚠️ Reached cycle LLM call limit. Stopping.")
                break
            await process_item(item)
            llm_calls += 3

def job():
    print("\n⏰ Running scheduled job...")
    try:
        asyncio.run(fetch_all_and_process())
        print("✅ Job completed.")
        from core.classification.dedup import cleanup_memory_cache
        cleanup_memory_cache()
        import gc
        gc.collect()
    except Exception as e:
        print(f"❌ Job failed: {e}")

def analytics_job():
    print("📊 Running weekly analytics...")
    run_weekly_analytics()
    print("✅ Analytics complete.")

def main():
    schedule.every(30).minutes.do(job)
    schedule.every(10).minutes.do(lambda: asyncio.run(fetch_fast_feeds()))
    schedule.every().tuesday.at("02:00").do(analytics_job)
    schedule.every().day.at("03:00").do(daily_backup_job)
    print("Scheduler started — news every 30 min, analytics on Monday 02:00.")
    job()
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()
