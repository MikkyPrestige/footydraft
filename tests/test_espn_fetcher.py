"""Quick manual test for ESPNFetcher. Run with: python -m tests.test_espn_fetcher"""
import asyncio
from core.ingestion.espn_fetcher import ESPNFetcher

async def main():
    fetcher = ESPNFetcher()
    print("Checking ESPN for live CL matches…")
    items = await fetcher.fetch()
    print(f"Found {len(items)} items")
    for item in items[:5]:
        print(f"[{item.source}] {item.title}")

if __name__ == "__main__":
    asyncio.run(main())
