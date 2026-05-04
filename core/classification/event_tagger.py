"""Keyword-based event classifier for NewsItems."""
from core.ingestion.base import NewsItem

PATTERNS = {
    "STAT_INSIGHT": [
        "stats", "statistics", "xG", "expected goals", "pass completion",
        "tackles won", "interceptions", "clearances", "duels won",
        "assists", "key passes", "heatmap", "rating", "average",
        "most chances created", "touches", "saves", "clean sheet",
        "possession", "passes", "distance covered",
        "xA", "expected assists", "progressive passes", "progressive carries",
        "field tilt", "PPDA", "passes per defensive action", "high press",
        "low block", "mid-block", "pressing intensity", "ball recoveries",
        "aerial duels", "shot map", "radar", "per 90", "touches in box",
        "final third entries", "cross completion", "dribbles completed",
        "fouls drawn", "offensive duels", "defensive duels", "through balls",
        "long balls", "accurate long balls", "big chances", "big chances missed",
        "goals prevented", "post-shot xG", "xGOT", "overperformance",
        "underperformance", "shot-creating actions", "goal-creating actions",
        "carries", "take-ons", "miscontrols", "dispossessed", "blocks",
        "pressures", "successful pressures", "attacking third", "middle third",
        "defensive third"
    ],
    "TRANSFER": [
        "transfer", "signs", "signed", "bid", "rumour", "deal", "contract",
        "loan", "offered", "target", "free agent", "release clause",
        "transfer window", "deadline day", "medical", "agreed terms",
        "set to join", "close to signing", "moves for", "in talks",
        "here we go", "advanced negotiations", "verbal agreement", "ultimatum",
        "telenovela", "summer saga", "on the radar", "shortlist", "courtship",
        "inquiry", "hot lead", "packing his bags", "one foot out", "war chest",
        "kitty", "bidding war", "auction", "marquee signing", "star signing",
        "bombshell", "breaks the market", "free transfer", "Bosman",
        "pre-contract", "buyout clause", "triggered", "activates",
        "wage demands", "personal terms", "entourage", "on the agenda",
        "white smoke", "deal collapses", "deal cools", "hijack", "gazump"
    ],
    "MEME": [
        "meme", "😂", "💀", "👀", "shithousery", "banter", "troll",
        "crying", "laugh", "funny", "joke", "wild", "unreal",
        "cant believe", "can't believe", "imagine", "only in",
        "peak football", "scripted", "madness",
        "bottle", "bottled", "bottle job", "finished club", "finished player",
        "fraud check", "washed king", "streets won't forget", "cold",
        "generational", "cooking", "let him cook", "he's cooking", "vibes",
        "vibes FC", "back him", "sell him", "sent him", "sent him to the shops",
        "no way", "no chance", "I've seen enough", "build the statue", "tears",
        "rent free", "living rent free", "obsessed", "ratio", "agenda",
        "pushing an agenda", "fanbase in the mud", "in the mud", "clear",
        "levels", "it's the history", "it's who we are", "we move",
        "packwatch", "RIP bozo", "finished"
    ],
    "DEBATE": [
        "debate", "controversial", "should have", "should've", "agree",
        "disagree", "hot take", "unpopular opinion", "argue", "arguably",
        "better than", "vs", "versus", "rival", "who is", "best player",
        "top 5", "top 10", "ranking", "compare", "comparison", "thread",
        "who's better", "overrated", "underrated", "fraud", "finished",
        "washed", "clear of", "levels above", "best in the world",
        "GOAT debate", "mount rushmore", "my manager", "my striker",
        "my winger", "prove me wrong", "change my mind",
        "the hill I'll die on", "he's not that guy", "different gravy",
        "build around", "if you disagree", "you're wrong", "don't @ me",
        "hot take incoming", "unpopular opinion incoming", "let's be real"
    ],
    "LIVE_GOAL": [
        "goal", "scores", "scored", "hat-trick", "hattrick", "penalty scored",
        "free-kick goal", "header goal", "volley goal", "curler", "tap-in",
        "equaliser", "winner", "opener", "brace",
        "strike", "finish", "netted", "converted", "slotted home", "fired in",
        "headed home", "long-range", "thunderbolt", "rocket", "screamer",
        "worldie", "backheel", "overhead kick", "bicycle kick", "deflected",
        "own goal", "last-gasp", "injury-time winner", "stoppage-time",
        "penalty", "from the spot", "converts", "puts [team] ahead",
        "doubles the lead", "pulls one back", "levels", "draws level",
        "equalises", "makes it [score]"
    ],
    "LIVE_CARD": [
        "red card", "yellow card", "sent off", "second yellow", "straight red",
        "dismissed", "booked", "cautioned", "ejection",
        "shown a red", "shown a yellow", "given his marching orders",
        "off for", "early bath", "sees red", "brandishes", "flashes",
        "VAR review", "upgraded to red", "downgraded",
        "retrospective ban", "suspension"
    ],
}

LIVE_INDICATORS = [
    "minute", "half-time", "halftime", "full-time", "kick-off",
    "substitution", "subbed", "injury", "stoppage", "added time",
    "penalty shootout", "extra time", "var", "overturned",
    "1h", "2h", "ht", "ft", "elapsed"
]

def classify_item(item: NewsItem) -> str:
    text = f"{item.title} {item.raw_text}".lower()
    # Check specific tags first (STAT_INSIGHT, TRANSFER, etc.)
    for tag, keywords in PATTERNS.items():
        if any(kw in text for kw in keywords):
            return tag
    # Then check generic live indicators
    if any(ind in text for ind in LIVE_INDICATORS):
        return "LIVE_OTHER"
    return "OTHER"
