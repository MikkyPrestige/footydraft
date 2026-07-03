import asyncio
from datetime import datetime
from typing import List
import requests
from core.ingestion.base import BaseFetcher, NewsItem
from core.ingestion.monitor import record_success, record_failure

SCOREBOARD_URLS = [
    # UEFA competitions
    "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.champions/scoreboard",
    "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.europa/scoreboard",
    "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.europa.conf/scoreboard",
    # Domestic cups
    "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.fa/scoreboard",
    "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.league_cup/scoreboard",
    "https://site.api.espn.com/apis/site/v2/sports/soccer/ita.coppa_italia/scoreboard",
    "https://site.api.espn.com/apis/site/v2/sports/soccer/ger.dfb_pokal/scoreboard",
    "https://site.api.espn.com/apis/site/v2/sports/soccer/esp.copa_del_rey/scoreboard",
    "https://site.api.espn.com/apis/site/v2/sports/soccer/fra.coupe_de_france/scoreboard",
]

LIVE_STATES = {"in"}

class ESPNFetcher(BaseFetcher):
    def __init__(self, max_entries: int = None):
        self.max_entries = max_entries

    async def fetch(self) -> List[NewsItem]:
        items = []
        try:
            for scoreboard_url in SCOREBOARD_URLS:
                data = await asyncio.to_thread(self._get_json, scoreboard_url)
                events = data.get("events", [])
                if self.max_entries is not None:
                    events = events[:self.max_entries]

                for event in events:
                    status = event.get("status", {}).get("type", {})
                    state = status.get("state", "")

                    if state not in LIVE_STATES:
                        continue

                    event_id = event["id"]
                    competitions = event.get("competitions", [])
                    if not competitions:
                        continue

                    comp = competitions[0]
                    competitors = comp.get("competitors", [])
                    if len(competitors) < 2:
                        continue

                    home = competitors[0]["team"]["displayName"]
                    away = competitors[1]["team"]["displayName"]
                    home_score = competitors[0].get("score", "0")
                    away_score = competitors[1].get("score", "0")
                    detail = status.get("detail", state)
                    short_detail = status.get("shortDetail", detail)

                    items.append(NewsItem(
                        title=f"📢 {home} vs {away} – {short_detail} ({home_score}-{away_score})",
                        url=f"https://www.espn.com/soccer/match/_/gameId/{event_id}",
                        source="ESPN",
                        published=datetime.utcnow(),
                        raw_text=f"Match status: {detail}, score: {home_score}-{away_score}"
                    ))

                    summary_base = scoreboard_url.replace("scoreboard", "summary")
                    summary_url = f"{summary_base}?event={event_id}"
                    try:
                        summary = await asyncio.to_thread(self._get_json, summary_url)
                        for key in ("scoringPlays", "plays"):
                            plays = summary.get(key, [])
                            if not plays:
                                continue
                            for play in plays:
                                text = play.get("text", "")
                                if not text:
                                    continue
                                team_name = play.get("team", {}).get("displayName", "")
                                period = play.get("period", {}).get("number", "")
                                clock = play.get("clock", {}).get("displayValue", "")

                                if any(kw in text.lower() for kw in ("goal", "penalty", "card", "red", "yellow", "substitution")):
                                    items.append(NewsItem(
                                        title=f"📢 {text}",
                                        url=f"https://www.espn.com/soccer/match/_/gameId/{event_id}",
                                        source="ESPN",
                                        published=datetime.utcnow(),
                                        raw_text=text
                                    ))
                    except Exception:
                        pass

            # Record success — silently ignore if table doesn't exist
            try:
                record_success("ESPN")
            except Exception:
                pass  # Table doesn't exist yet — safe to ignore

        except Exception as e:
            # Record failure — silently ignore if table doesn't exist
            try:
                record_failure("ESPN")
            except Exception:
                pass  # Table doesn't exist yet — safe to ignore
            print(f"ESPN fetch failed: {e}")

        return items

    def _get_json(self, url: str):
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.json()


# import asyncio
# from datetime import datetime
# from typing import List
# import requests
# from core.ingestion.base import BaseFetcher, NewsItem
# from core.ingestion.monitor import record_success, record_failure

# SCOREBOARD_URLS = [
#     # UEFA competitions
#     "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.champions/scoreboard",
#     "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.europa/scoreboard",
#     "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.europa.conf/scoreboard",
#     # Domestic cups
#     "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.fa/scoreboard",
#     "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.league_cup/scoreboard",
#     "https://site.api.espn.com/apis/site/v2/sports/soccer/ita.coppa_italia/scoreboard",
#     "https://site.api.espn.com/apis/site/v2/sports/soccer/ger.dfb_pokal/scoreboard",
#     "https://site.api.espn.com/apis/site/v2/sports/soccer/esp.copa_del_rey/scoreboard",
#     "https://site.api.espn.com/apis/site/v2/sports/soccer/fra.coupe_de_france/scoreboard",
# ]

# LIVE_STATES = {"in"}

# class ESPNFetcher(BaseFetcher):
#     def __init__(self, max_entries: int = None):
#         self.max_entries = max_entries

#     async def fetch(self) -> List[NewsItem]:
#         items = []
#         try:
#             for scoreboard_url in SCOREBOARD_URLS:
#                 data = await asyncio.to_thread(self._get_json, scoreboard_url)
#                 events = data.get("events", [])
#                 if self.max_entries is not None:
#                     events = events[:self.max_entries]

#                 for event in events:
#                     status = event.get("status", {}).get("type", {})
#                     state = status.get("state", "")

#                     if state not in LIVE_STATES:
#                         continue

#                     event_id = event["id"]
#                     competitions = event.get("competitions", [])
#                     if not competitions:
#                         continue

#                     comp = competitions[0]
#                     competitors = comp.get("competitors", [])
#                     if len(competitors) < 2:
#                         continue

#                     home = competitors[0]["team"]["displayName"]
#                     away = competitors[1]["team"]["displayName"]
#                     home_score = competitors[0].get("score", "0")
#                     away_score = competitors[1].get("score", "0")
#                     detail = status.get("detail", state)
#                     short_detail = status.get("shortDetail", detail)

#                     items.append(NewsItem(
#                         title=f"📢 {home} vs {away} – {short_detail} ({home_score}-{away_score})",
#                         url=f"https://www.espn.com/soccer/match/_/gameId/{event_id}",
#                         source="ESPN",
#                         published=datetime.utcnow(),
#                         raw_text=f"Match status: {detail}, score: {home_score}-{away_score}"
#                     ))

#                     summary_base = scoreboard_url.replace("scoreboard", "summary")
#                     summary_url = f"{summary_base}?event={event_id}"
#                     try:
#                         summary = await asyncio.to_thread(self._get_json, summary_url)
#                         for key in ("scoringPlays", "plays"):
#                             plays = summary.get(key, [])
#                             if not plays:
#                                 continue
#                             for play in plays:
#                                 text = play.get("text", "")
#                                 if not text:
#                                     continue
#                                 team_name = play.get("team", {}).get("displayName", "")
#                                 period = play.get("period", {}).get("number", "")
#                                 clock = play.get("clock", {}).get("displayValue", "")

#                                 if any(kw in text.lower() for kw in ("goal", "penalty", "card", "red", "yellow", "substitution")):
#                                     items.append(NewsItem(
#                                         title=f"📢 {text}",
#                                         url=f"https://www.espn.com/soccer/match/_/gameId/{event_id}",
#                                         source="ESPN",
#                                         published=datetime.utcnow(),
#                                         raw_text=text
#                                     ))
#                     except Exception:
#                         pass

#     # Only record if source_health table exists
#                        # Only record if source_health table exists
#             try:
#                 record_success("ESPN")
#             except Exception:
#                 pass  # Table doesn't exist yet — safe to ignore
#         except Exception as e:
#             try:
#                 record_failure("ESPN")
#             except Exception:
#                 pass  # Table doesn't exist yet — safe to ignore
#             print(f"ESPN fetch failed: {e}")
#         return items

#     def _get_json(self, url: str):
#         resp = requests.get(url, timeout=15)
#         resp.raise_for_status()
#         return resp.json()
