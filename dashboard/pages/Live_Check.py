"""Live Check – run live match checks automatically and show results directly."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import streamlit as st
import pandas as pd
import asyncio
from datetime import datetime, timedelta
from requests.exceptions import ConnectionError, Timeout

from dashboard.utils import restore_backup_state
from dashboard.ui_components import apply_global_styles, render_sidebar

# Attempt auto‑restore (safe – any errors will be caught below)
try:
    restore_backup_state()
except Exception:
    pass  # We'll handle it in the main flow

st.set_page_config(
    page_title="Live Check",
    layout="wide",
    page_icon="dashboard/static/favicon.ico"
)

# Inject global styles and render sidebar
apply_global_styles()
render_sidebar()

st.title(":material/search: Live Check")

st.write("Results update automatically when you open the page. Use the button below to refresh.")


# ---------- Cached fetch function ----------
@st.cache_data(ttl=300)  # 5-minute cache
def fetch_live_data():
    """Fetch live data from API‑Football and ESPN. Cached for performance."""
    results = {}

    # ---------- API‑Football ----------
    try:
        from core.ingestion.api_football_fetcher import APIFootballFetcher
        fetcher = APIFootballFetcher()
        items = asyncio.run(fetcher.fetch())
        if not items:
            yesterday = (datetime.utcnow() - timedelta(hours=2)).strftime("%Y-%m-%d")
            fetcher2 = APIFootballFetcher(match_date=yesterday)
            items = asyncio.run(fetcher2.fetch())
        results["API‑Football"] = items
    except Exception as e:
        # Return None so we don't cache errors
        return None

    # ---------- ESPN ----------
    try:
        from core.ingestion.espn_fetcher import ESPNFetcher
        espn = ESPNFetcher()
        items_espn = asyncio.run(espn.fetch())
        results["ESPN"] = items_espn
    except Exception as e:
        # Return None so we don't cache errors
        return None

    return results


# ---------- Button: force refresh ----------
if st.button("Run Live Check"):
    # Clear cache so next call to fetch_live_data() will re‑fetch
    st.cache_data.clear()
    st.rerun()  # reload the page to show fresh data


# ---------- Display ----------
results = fetch_live_data()  # This will return cached data unless cleared

# Check if any source returned an error string
error_sources = []
display_data = {}

for source, data in results.items():
    if isinstance(data, str) and data.startswith("ERROR:"):
        error_sources.append(f"{source}: {data}")
    else:
        display_data[source] = data

# Show errors if any
if error_sources:
    for err in error_sources:
        st.error(f":material/error: {err}")

if display_data:
    for source, items in display_data.items():
        with st.expander(f"{source} ({len(items)} events)"):
            if not items:
                st.info(f":material/inbox: No live matches from {source}.")
                continue
            # We need classify_item here — import it inside to avoid global import issues
            from core.classification.event_tagger import classify_item
            rows = []
            for item in items:
                tag = classify_item(item)
                rows.append({"Tag": tag, "Title": item.title, "Time": item.published})
            df = pd.DataFrame(rows)
            st.dataframe(df, width='stretch')
else:
    # If no display_data (all sources errored), show info
    if not display_data and not error_sources:
        st.info(":material/inbox: No results yet. Click 'Run Live Check' to fetch live matches.")
    elif not display_data and error_sources:
        st.info(":material/inbox: No data available due to errors above.")