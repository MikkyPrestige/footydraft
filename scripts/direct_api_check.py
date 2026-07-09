import requests
from datetime import datetime
from config.settings import API_FOOTBALL_KEY

headers = {"x-apisports-key": API_FOOTBALL_KEY}

# 1. Live=all
resp1 = requests.get("https://v3.football.api-sports.io/fixtures?live=all", headers=headers)
data1 = resp1.json()
print("Live=all results:", data1.get("results", 0))
for f in data1.get("response", [])[:2]:
    print(f['fixture']['id'], f['teams']['home']['name'], "vs", f['teams']['away']['name'], f['fixture']['status']['short'])

# 2. Today's date
today = datetime.utcnow().strftime("%Y-%m-%d")
resp2 = requests.get(f"https://v3.football.api-sports.io/fixtures?date={today}", headers=headers)
data2 = resp2.json()
print(f"\nFixtures for {today}:", data2.get("results", 0))
for f in data2.get("response", [])[:2]:
    print(f['fixture']['id'], f['teams']['home']['name'], "vs", f['teams']['away']['name'], f['fixture']['status']['short'])
