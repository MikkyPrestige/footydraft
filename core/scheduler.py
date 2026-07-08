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

LEADERBOARD_COMPETITIONS = [
    ("World Cup", 2000),
    ("Premier League", 2021),
    ("La Liga", 2014),
    ("Bundesliga", 2002),
    ("Serie A", 2019),
    ("Ligue 1", 2015),
    ("Champions League", 2001),
]

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

    # Process only 1 item per fast cycle (keeps Groq token usage safe)
    if relevant:
        await process_item(relevant[0])

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

async def fetch_and_draft_leaderboards():
    """Fetch top scorers & assists for all active competitions and create drafts."""
    import os
    import requests
    from core.ingestion.base import NewsItem
    from core.generation.queue_manager import process_item

    key = os.getenv("FOOTBALL_DATA_KEY")
    if not key:
        print("📊 Leaderboard: No FOOTBALL_DATA_KEY set.")
        return

    for comp_name, comp_id in LEADERBOARD_COMPETITIONS:
        try:
            resp = requests.get(
                f"https://api.football-data.org/v4/competitions/{comp_id}/scorers",
                headers={"X-Auth-Token": key},
                timeout=15
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"📊 {comp_name} leaderboard fetch failed: {e}")
            continue

        scorers = data.get("scorers", [])
        if not scorers:
            print(f"📊 {comp_name}: No scorer data available — skipping.")
            continue

        lines = [f"🏆 {comp_name} — Top Scorers & Assists", ""]

        # Top Scorers
        lines.append("⚽ Top Scorers:")
        for i, s in enumerate(scorers[:10], start=1):
            name = s["player"]["name"]
            goals = s.get("goals", 0)
            lines.append(f"{i}. {name} — {goals} goals")
        lines.append("")

        # Top Assists
        by_assists = sorted(
            [s for s in scorers if s.get("assists")],
            key=lambda x: x["assists"],
            reverse=True
        )[:5]
        if by_assists:
            lines.append("🅰️ Top Assists:")
            for i, s in enumerate(by_assists, start=1):
                name = s["player"]["name"]
                assists = s["assists"]
                lines.append(f"{i}. {name} — {assists} assists")
            lines.append("")

        raw = "\n".join(lines)
        item = NewsItem(
            title=f"🏆 {comp_name} Stats Leaderboard — {datetime.utcnow().strftime('%b %d')}",
            url="https://www.fifa.com/worldcup/" if comp_id == 2000 else "",
            source="Football-Data.org",
            published=datetime.utcnow(),
            raw_text=raw
        )
        await process_item(item)
        print(f"📊 {comp_name} leaderboard draft created.")

async def nerdy_stats_job():
    """Analyse stored match stats and create a draft with nerdy insights."""
    from core.database import SessionLocal
    from core.models import MatchStats
    from core.ingestion.base import NewsItem
    from core.generation.queue_manager import process_item
    from sqlalchemy import or_

    with SessionLocal() as session:
        # Get all stats from the last 7 days
        cutoff = datetime.utcnow() - timedelta(days=7)
        rows = session.query(MatchStats).filter(
            MatchStats.created_at >= cutoff
        ).all()

    if not rows:
        print("🧠 Nerdy stats: No matches in the last 7 days.")
        return

    insights = []
    insights.append("🧠 Nerdy Stats of the Week\n")

    # 1. Biggest xG overperformance (scored ≥2 more than xG)
    best_overperform = None
    best_diff = 0
    for r in rows:
        for side, goals, xg in [("home", r.home_goals, r.xg_home), ("away", r.away_goals, r.xg_away)]:
            if xg is not None and goals - xg >= 2:
                diff = goals - xg
                if diff > best_diff:
                    best_diff = diff
                    best_overperform = (r.home_team if side == "home" else r.away_team, r, goals, xg)
    if best_overperform:
        team, r, goals, xg = best_overperform
        insights.append(f"📈 xG Overperformers: {team} scored {goals} from just {xg:.2f} xG (+{best_diff:.2f}) vs {r.away_team if team == r.home_team else r.home_team}")

    # 2. Possession in vain (≥60% possession but lost)
    for r in rows:
        if r.possession_home is not None and r.possession_away is not None:
            if r.possession_home >= 60 and r.home_goals < r.away_goals:
                insights.append(f"😵 Possession in vain: {r.home_team} had {r.possession_home:.0f}% possession but lost {r.home_goals}-{r.away_goals} to {r.away_team}")
            if r.possession_away >= 60 and r.away_goals < r.home_goals:
                insights.append(f"😵 Possession in vain: {r.away_team} had {r.possession_away:.0f}% possession but lost {r.away_goals}-{r.home_goals} to {r.home_team}")

    # 3. Shot barrage (most total shots)
    best_shots = max(rows, key=lambda r: (r.total_shots_home or 0) + (r.total_shots_away or 0), default=None)
    if best_shots and (best_shots.total_shots_home or 0) + (best_shots.total_shots_away or 0) > 30:
        total = (best_shots.total_shots_home or 0) + (best_shots.total_shots_away or 0)
        insights.append(f"💥 Shot Barrage: {best_shots.home_team} vs {best_shots.away_team} had {total} total shots")

    # 4. Passing masterclass (most total passes)
    best_passes = max(rows, key=lambda r: (r.passes_home or 0) + (r.passes_away or 0), default=None)
    if best_passes and (best_passes.passes_home or 0) + (best_passes.passes_away or 0) > 1000:
        total_p = (best_passes.passes_home or 0) + (best_passes.passes_away or 0)
        insights.append(f"🎯 Passing Masterclass: {best_passes.home_team} vs {best_passes.away_team} combined {total_p} passes")

    # 5. xG shutout (won with opponent xG ≤ 0.5)
    for r in rows:
        if r.home_goals > r.away_goals and r.xg_away is not None and r.xg_away <= 0.5:
            insights.append(f"🔒 xG Shutout: {r.home_team} beat {r.away_team} {r.home_goals}-{r.away_goals}, conceding only {r.xg_away:.2f} xG")
        if r.away_goals > r.home_goals and r.xg_home is not None and r.xg_home <= 0.5:
            insights.append(f"🔒 xG Shutout: {r.away_team} beat {r.home_team} {r.away_goals}-{r.home_goals}, conceding only {r.xg_home:.2f} xG")

    if len(insights) == 1:
        print("🧠 Nerdy stats: No unusual findings this week.")
        return

    raw = "\n".join(insights)
    item = NewsItem(
        title=f"🧠 Nerdy Stats of the Week — {datetime.utcnow().strftime('%b %d')}",
        url="",
        source="API-Football",
        published=datetime.utcnow(),
        raw_text=raw
    )
    await process_item(item)
    print("🧠 Nerdy stats draft created.")

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
    schedule.every(15).minutes.do(lambda: asyncio.run(fetch_fast_feeds()))
    schedule.every().monday.at("02:00").do(lambda: asyncio.run(fetch_and_draft_leaderboards()))
    schedule.every().thursday.at("02:00").do(lambda: asyncio.run(fetch_and_draft_leaderboards()))
    schedule.every().tuesday.at("03:00").do(lambda: asyncio.run(nerdy_stats_job()))
    schedule.every().tuesday.at("02:00").do(analytics_job)
    schedule.every().day.at("03:00").do(daily_backup_job)
    print("Scheduler started — news every 30 min, analytics on Monday 02:00.")
    job()
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()
