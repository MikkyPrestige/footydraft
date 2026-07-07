import asyncio
from datetime import datetime, timedelta
from typing import List
from urllib.parse import quote
import feedparser
from core.ingestion.base import BaseFetcher, NewsItem
from core.ingestion.monitor import record_success, record_failure

# Keywords match the build plan: football, premier league, champions league
SEARCH_QUERY = "football OR premier league OR champions league OR transfer OR soccer"
BASE_URL = "https://news.google.com/rss/search?q={}&hl=en-GB&gl=GB&ceid=GB:en"

class GoogleNewsFetcher(BaseFetcher):
    def __init__(self, search_query: str = None, max_entries: int = None):
        self.search_query = search_query or SEARCH_QUERY
        self.max_entries = max_entries

    async def fetch(self) -> List[NewsItem]:
        items = []
        try:
            url = BASE_URL.format(quote(self.search_query))
            # feedparser is blocking → run in thread
            feed = await asyncio.to_thread(feedparser.parse, url)
            entries = feed.entries
            if self.max_entries is not None:
                entries = entries[:self.max_entries]
            for entry in entries:
                if not hasattr(entry, "published_parsed") or not entry.published_parsed:
                    continue
                published = datetime(*entry.published_parsed[:6])
                if (datetime.utcnow() - published) > timedelta(hours=12):
                    continue
                items.append(NewsItem(
                    title=entry.title,
                    url=entry.link,
                    source="Google News",
                    published=published,
                    raw_text=entry.get("summary", "")
                ))
            record_success("Google News")
        except Exception as e:
            record_failure("Google News")
            print(f"Google News fetch failed: {e}")
        return items
