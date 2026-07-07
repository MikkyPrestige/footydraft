import asyncio
from datetime import datetime, timedelta
from typing import List
import requests
from core.ingestion.base import BaseFetcher, NewsItem
from core.ingestion.monitor import record_success, record_failure

SUBREDDIT = "soccer"
REDDIT_URL = f"https://www.reddit.com/r/{SUBREDDIT}/new.json"
HEADERS = {"User-Agent": "football-agent v1.0 (anonymized)"}

class RedditFetcher(BaseFetcher):
    def __init__(self, max_entries: int = None):
        self.max_entries = max_entries

    async def fetch(self) -> List[NewsItem]:
        items = []
        try:
            # Run the blocking request in a thread
            def get_json():
                resp = requests.get(REDDIT_URL, headers=HEADERS, timeout=15)
                resp.raise_for_status()
                return resp.json()
            data = await asyncio.to_thread(get_json)
            children = data.get("data", {}).get("children", [])
            if self.max_entries is not None:
                children = children[:self.max_entries]
            for child in children:
                post = child["data"]
                published = datetime.utcfromtimestamp(post["created_utc"])
                if (datetime.utcnow() - published) > timedelta(hours=12):
                    continue
                items.append(NewsItem(
                    title=post["title"],
                    url=f"https://reddit.com{post['permalink']}",
                    source="Reddit r/soccer",
                    published=datetime.utcfromtimestamp(post["created_utc"]),
                    raw_text=post.get("selftext", "")
                ))
            record_success("Reddit r/soccer")
        except Exception as e:
            record_failure("Reddit r/soccer")
            print(f"Reddit fetch failed: {e}")
        return items
