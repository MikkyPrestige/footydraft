import asyncio
from datetime import datetime
from typing import List, Optional
import requests
from config.settings import API_FOOTBALL_KEY
from core.ingestion.base import BaseFetcher, NewsItem
from core.ingestion.monitor import record_success, record_failure
from core.database import SessionLocal
from core.models import EventCache

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

            record_success("API-Football")

             # --- Post‑match stat packs ---
            for fixture in merged:
                status = fixture["fixture"]["status"]["short"]
                if status not in ("FT", "AET", "PEN"):
                    continue
                fid = fixture["fixture"]["id"]
                if self._stats_already_processed(fid):
                    continue

                home = fixture["teams"]["home"]["name"]
                away = fixture["teams"]["away"]["name"]
                home_goals = fixture["goals"]["home"]
                away_goals = fixture["goals"]["away"]
                score = f"{home} {home_goals}-{away_goals} {away}"

                try:
                    stats_data = await asyncio.to_thread(
                        self._get_json,
                        f"{BASE_URL}/fixtures/statistics?fixture={fid}"
                    )
                    stats_raw = stats_data.get("response", [])
                except Exception:
                    stats_raw = []

                if not stats_raw:
                    # still mark as processed so we don't keep trying
                    self._mark_stats_processed(fid)
                    continue

                # Build a readable stats string
                lines = [score, ""]
                for team_stats in stats_raw:
                    team_name = team_stats["team"]["name"]
                    lines.append(f"--- {team_name} ---")
                    for stat in team_stats.get("statistics", [])[:8]:   # top 8 stats
                        stat_name = stat.get("type", "")
                        stat_value = stat.get("value", "")
                        if stat_value is not None:
                            lines.append(f"{stat_name}: {stat_value}")
                    lines.append("")

                stat_text = "\n".join(lines)

                items.append(NewsItem(
                    title=f"📊 FT Stat Pack: {home} vs {away}",
                    url=f"https://www.flashscore.com/match/{fid}",
                    source="API-Football Stats",
                    published=datetime.utcnow(),
                    raw_text=stat_text
                ))

                self._mark_stats_processed(fid)

            # --- Half‑time stat packs ---
            for fixture in merged:
                status = fixture["fixture"]["status"]["short"]
                if status != "HT":
                    continue
                fid = fixture["fixture"]["id"]
                if self._stats_already_processed(fid, tag="stats_ht"):
                    continue

                home = fixture["teams"]["home"]["name"]
                away = fixture["teams"]["away"]["name"]
                home_goals = fixture["goals"]["home"]
                away_goals = fixture["goals"]["away"]
                score = f"{home} {home_goals}-{away_goals} {away}"

                try:
                    stats_data = await asyncio.to_thread(
                        self._get_json,
                        f"{BASE_URL}/fixtures/statistics?fixture={fid}"
                    )
                    stats_raw = stats_data.get("response", [])
                except Exception:
                    stats_raw = []

                if not stats_raw:
                    self._mark_stats_processed(fid, tag="stats_ht")
                    continue

                lines = [f"⏸️ HT Stat Pack: {score}", ""]
                for team_stats in stats_raw:
                    team_name = team_stats["team"]["name"]
                    lines.append(f"--- {team_name} ---")
                    for stat in team_stats.get("statistics", [])[:8]:
                        stat_name = stat.get("type", "")
                        stat_value = stat.get("value", "")
                        if stat_value is not None:
                            lines.append(f"{stat_name}: {stat_value}")
                    lines.append("")

                stat_text = "\n".join(lines)

                items.append(NewsItem(
                    title=f"📊 HT Stat Pack: {home} vs {away}",
                    url=f"https://www.flashscore.com/match/{fid}",
                    source="API-Football Stats",
                    published=datetime.utcnow(),
                    raw_text=stat_text
                ))

                self._mark_stats_processed(fid, tag="stats_ht")

        except Exception as e:

            record_failure("API-Football")
            print(f"API-Football fetch failed: {e}")
        return items

    def _get_json(self, url: str):
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def _stats_already_processed(self, fixture_id: int, tag: str = "stats") -> bool:
        try:
            with SessionLocal() as session:
                exists = session.query(EventCache).filter(
                    EventCache.event_id == f"{tag}_{fixture_id}",
                    EventCache.created_at >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                ).first()
                return exists is not None
        except Exception:
            return False

    def _mark_stats_processed(self, fixture_id: int, tag: str = "stats"):
        try:
            with SessionLocal() as session:
                entry = EventCache(event_id=f"{tag}_{fixture_id}")
                session.add(entry)
                session.commit()
        except Exception:
            pass