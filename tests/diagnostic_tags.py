"""Diagnose event tag distribution from all news sources."""
import asyncio
from core.ingestion.rss_fetcher import RSSFetcher
from core.ingestion.reddit_fetcher import RedditFetcher
from core.ingestion.google_news_fetcher import GoogleNewsFetcher
from core.classification.event_tagger import classify_item

STATS_QUERY = "football statistics OR xG OR expected goals OR progressive passes OR shot map OR heat map OR big chances OR passing accuracy OR tackles OR interceptions"

async def main():
    fetchers = [
        ("RSS", RSSFetcher()),
        ("Reddit", RedditFetcher()),
        ("Google News", GoogleNewsFetcher()),
        ("Google Stats", GoogleNewsFetcher(search_query=STATS_QUERY)),
    ]
    print("Fetching news and classifying tags…\n")
    tag_counts = {}
    total = 0
    for name, fetcher in fetchers:
        items = await fetcher.fetch()
        print(f"{name}: {len(items)} items")
        for item in items:
            tag = classify_item(item)
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
            total += 1

    print(f"\nTotal items classified: {total}\n")
    print("Tag distribution:")
    for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1]):
        pct = (count / total * 100) if total > 0 else 0
        print(f"{tag:20s} {count:4d} ({pct:.1f}%)")

if __name__ == "__main__":
    asyncio.run(main())
