"""Diagnostic: check API‑Football live data and event classification."""
import asyncio
from datetime import datetime
from core.ingestion.api_football_fetcher import APIFootballFetcher
from core.classification.event_tagger import classify_item

async def main():
    fetcher = APIFootballFetcher()
    print("🔄 Fetching live fixtures (API‑Football)...")
    items = await fetcher.fetch()
    print(f"   Returned {len(items)} items.\n")

    if items:
        print("   📋 First 5 items and their tags:")
        for item in items[:5]:
            tag = classify_item(item)
            print(f"   [{tag}] {item.title}")
    else:
        print("   ⚠️ No live items returned. Possible causes:")
        print("      - No matches are currently live")
        print("      - Free‑tier rate limit exhausted")
        print("      - League filter blocked the match")
        print("      - Match status not in accepted list (1H/HT/2H/FT)")
        print()
        # Fetch today's CL fixtures without live filter to see what happened
        print("🔄 Fetching today's fixtures without live filter...")
        import requests
        from config.settings import API_FOOTBALL_KEY
        headers = {"x-apisports-key": API_FOOTBALL_KEY}
        resp = requests.get(
            "https://v3.football.api-sports.io/fixtures?league=2&season=2026&date="
            + datetime.utcnow().strftime("%Y-%m-%d"),
            headers=headers, timeout=10
        )
        data = resp.json()
        fixtures = data.get("response", [])
        print(f"   Found {len(fixtures)} fixtures for Champions League (league ID 2) today.")
        for fix in fixtures[:3]:
            f = fix["fixture"]
            print(f"   {f['id']}: {fix['teams']['home']['name']} vs {fix['teams']['away']['name']} "
                  f"– status: {f['status']['short']} ({f['status']['long']})")

if __name__ == "__main__":
    asyncio.run(main())
