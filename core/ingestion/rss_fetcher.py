import asyncio
import feedparser
from datetime import datetime, timedelta
from typing import List
from core.ingestion.base import BaseFetcher, NewsItem
from core.ingestion.monitor import record_success, record_failure

FEEDS = {
    "BBC Sport": "http://feeds.bbci.co.uk/sport/football/rss.xml",
    "Sky Sports": "https://www.skysports.com/rss/12040",
    "ESPN FC": "https://www.espn.com/espn/rss/soccer/news",
    "The Guardian Football": "https://www.theguardian.com/football/rss",
    "Daily Mail Football": "https://www.dailymail.co.uk/sport/football/articles.rss",
    "Goal.com (via Feedburner)": "https://feeds.feedburner.com/goalnews",
    "The Guardian Football": "https://www.theguardian.com/football/series/football-daily/rss",
    "Sky Sports Football": "https://www.skysports.com/football/rss",
    "The Analyst (Opta)": "https://theanalyst.com/feed/",
    "FBref (StatsBomb)": "https://fbref.com/feed/",
}

FAST_FEEDS = {
    "BBC Gossip": "http://feeds.bbci.co.uk/sport/football/gossip/rss.xml",
    "ESPN FC Latest": "https://www.espn.com/espn/rss/soccer/news",
    "The Guardian Football": "https://www.theguardian.com/football/rss",
    "Daily Mail Football": "https://www.dailymail.co.uk/sport/football/articles.rss",
    "Metro Football": "https://metro.co.uk/sport/football/feed/",
    "talkSPORT Football": "https://talksport.com/football/feed/",
}

class RSSFetcher(BaseFetcher):
    def __init__(self, feeds: dict = None, max_entries: int = None):
        self.feeds = feeds or FEEDS
        self.max_entries = max_entries

    async def fetch(self) -> List[NewsItem]:
        items = []
        for source_name, url in self.feeds.items():
            try:
                feed = await asyncio.to_thread(feedparser.parse, url)
                entries = feed.entries
                if self.max_entries is not None:
                    entries = entries[:self.max_entries]
                for entry in entries:
                    if not hasattr(entry, 'published_parsed') or not entry.published_parsed:
                        continue
                    published = datetime(*entry.published_parsed[:6])
                    if (datetime.utcnow() - published) > timedelta(hours=12):
                         continue
                    items.append(NewsItem(
                        title=entry.title,
                        url=entry.link,
                        source=source_name,
                        published=published,
                        raw_text=entry.get('summary', '')
                    ))
                record_success(source_name)
            except Exception as e:
                record_failure(source_name)
                print(f'RSS fetch failed for {source_name}: {e}')
        return items
