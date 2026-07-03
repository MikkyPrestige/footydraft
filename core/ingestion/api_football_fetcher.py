import asyncio
from datetime import datetime, timedelta
from typing import List, Optional
import requests
from config.settings import API_FOOTBALL_KEY
from core.ingestion.base import BaseFetcher, NewsItem
from core.ingestion.monitor import record_success, record_failure

BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_FOOTBALL_KEY}

LEAGUE_IDS = [
    1,    # FIFA World Cup
    39,    # Premier League
    528,   # Community Shield
    45,    # FA Cup
    48,    # League Cup
    143,   # Copa del Rey
    140,   # La Liga
    78,    # Bundesliga
    81,    # DFB Pokal
    135,   # Serie A
    137,   # Coppa Italia
    66,    # Coupe de France
    61,    # Ligue 1
    2,     # UEFA Champions League
    3,     # UEFA Europa League
    848,   # UEFA Conference League
    826,   # Saudi Super Cup
    307,   # Saudi Pro League
    203,   # Turkish Süper Lig
    551,   # Turkish Super Cup
]
LEAGUE_IDS_SET = set(LEAGUE_IDS)
LIVE_STATUSES = {"1H", "HT", "2H", "LIVE", "FT"}

class APIFootballFetcher(BaseFetcher):
    def __init__(self, match_date: Optional[str] = None, max_entries: int = None):
        self.match_date = match_date
        self.max_entries = max_entries

    async def fetch(self) -> List[NewsItem]:
        items = []
        try:
            league_filter = "-".join(str(lid) for lid in LEAGUE_IDS)
            # 1. live=all (original)
            live_data = await asyncio.to_thread(
                self._get_json,
                f"{BASE_URL}/fixtures?live=all&league={league_filter}"
            )
            live_fixtures = live_data.get("response", [])

            # 2. today's complete fixture list (catches matches missing from live=all)
            today = datetime.utcnow().strftime("%Y-%m-%d")
            today_data = await asyncio.to_thread(
                self._get_json,
                f"{BASE_URL}/fixtures?date={today}"
            )
            today_fixtures = today_data.get("response", [])

            # Merge, deduplicate, keep only in‑play matches from date list
            seen_ids = set()
            merged = []

            for fix in live_fixtures:
                fid = fix["fixture"]["id"]
                seen_ids.add(fid)
                merged.append(fix)

            for fix in today_fixtures:
                fid = fix["fixture"]["id"]
                if fid in seen_ids:
                    continue
                seen_ids.add(fid)
                league_id = fix["league"]["id"]
                status = fix["fixture"]["status"]["short"]
                if league_id in LEAGUE_IDS_SET and status in LIVE_STATUSES:
                    merged.append(fix)

            if self.max_entries is not None:
                merged = merged[:self.max_entries]

            for fixture in merged:
                fixture_id = fixture["fixture"]["id"]
                home = fixture["teams"]["home"]["name"]
                away = fixture["teams"]["away"]["name"]
                status = fixture["fixture"]["status"]["short"]

                events_data = await asyncio.to_thread(
                    self._get_json,
                    f"{BASE_URL}/events?fixture={fixture_id}"
                )
                for evt in events_data.get("response", []):
                    event_type = evt["type"]
                    detail = evt.get("detail", "")
                    player = evt.get("player", {}).get("name", "Unknown")
                    team = evt["team"]["name"]
                    minute = evt["time"]["elapsed"]

                    if event_type == "Goal":
                        title = f"⚽ GOAL! {team} {detail} – {home} vs {away} ({minute}')"
                    elif event_type in ("Card", "Yellow Card", "Red Card"):
                        title = f"🟨 CARD: {player} ({team}) – {home} vs {away}"
                    elif event_type == "subst":
                        title = f"↔️ SUB: {player} – {home} vs {away}"
                    else:
                        continue

                    items.append(NewsItem(
                        title=title,
                        url=f"https://www.flashscore.com/match/{fixture_id}",
                        source="API-Football",
                        published=datetime.utcnow(),
                        raw_text=f"{event_type} by {player} at {minute}'"
                    ))

                if status in ("1H", "HT", "2H", "FT"):
                    items.append(NewsItem(
                        title=f"📢 {home} vs {away} – Status: {status}",
                        url=f"https://www.flashscore.com/match/{fixture_id}",
                        source="API-Football",
                        published=datetime.utcnow(),
                        raw_text=f"Match status: {status}"
                    ))

            # Record success — silently ignore if table doesn't exist
            try:
                record_success("API-Football")
            except Exception:
                pass  # Table doesn't exist yet — safe to ignore

        except Exception as e:
            # Record failure — silently ignore if table doesn't exist
            try:
                record_failure("API-Football")
            except Exception:
                pass  # Table doesn't exist yet — safe to ignore
            print(f"API-Football fetch failed: {e}")

        return items

    def _get_json(self, url: str):
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        return resp.json()