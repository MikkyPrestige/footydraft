"""Performance Analytics – engagement trends, persona breakdown, top tweets."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import streamlit as st
import pandas as pd
import altair as alt
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, DatabaseError

from dashboard.utils import restore_backup_state
from dashboard.ui_components import apply_global_styles, render_sidebar, require_auth

# Attempt auto‑restore (safe – any errors will be caught below)
try:
    restore_backup_state()
except Exception:
    pass  # handled in the main flow

st.set_page_config(
    page_title="Performance Analytics",
    layout="wide",
    page_icon="dashboard/static/favicon.ico"
)

# Inject global styles, render sidebar and authentication check
apply_global_styles()
render_sidebar()
require_auth()

st.title(":material/bar_chart: Performance Analytics")

# --- Check if backup is loaded ---
if not st.session_state.get("backup_loaded"):
    st.warning(":material/folder_open: No backup loaded. Use the sidebar to load a backup first.")
    st.stop()

engine = st.session_state.db_engine

# --- Validate engine ---
if engine is None:
    st.error(":material/folder_open: Database engine not available. Please reload your backup from the sidebar.")
    st.stop()

# --- Helper: safe query for DataFrame ---
def safe_query_to_df(query_text: str):
    """Execute a query and return a DataFrame. Return None on error."""
    try:
        with engine.connect() as conn:
            return pd.read_sql(text(query_text), conn)
    except (OperationalError, DatabaseError):
        return None
    except Exception:
        return None

# --- Engagement over time ---
st.header("Engagement Over Time")
df = safe_query_to_df("""
    SELECT DATE(posted_at) as day,
           SUM(likes) as likes,
           SUM(retweets) as retweets,
           SUM(replies) as replies,
           SUM(impressions) as impressions
    FROM tweets
    GROUP BY day
    ORDER BY day
""")
if df is None:
    st.info(":material/inbox: No tweet data available yet.")
elif df.empty:
    st.info(":material/inbox: No tweet data yet.")
else:
    df_melt = df.melt("day", var_name="metric", value_name="value")
    chart = alt.Chart(df_melt).mark_line(point=True).encode(
        x=alt.X("day:T", axis=alt.Axis(labelAngle=-45)),
        y="value:Q",
        color="metric:N",
        tooltip=["day", "metric", "value"]
    ).properties(height=350).interactive()
    st.altair_chart(chart, width='stretch')

# --- Persona breakdown ---
st.header("Average Likes by Persona")
pdf = safe_query_to_df("""
    SELECT d.persona, AVG(t.likes) as avg_likes, COUNT(*) as tweets
    FROM tweets t JOIN drafts d ON t.draft_id = d.id
    WHERE d.persona IS NOT NULL
    GROUP BY d.persona
    ORDER BY avg_likes DESC
""")
if pdf is None:
    st.info(":material/inbox: Could not load persona data. The table may be missing.")
elif pdf.empty:
    st.info(":material/inbox: No tweet data with persona yet.")
else:
    chart = alt.Chart(pdf).mark_bar().encode(
        x=alt.X("persona:N", sort="-y"),
        y="avg_likes:Q",
        color="persona:N",
        tooltip=["persona", "avg_likes", "tweets"]
    ).properties(height=300)
    st.altair_chart(chart, width='stretch')

# --- Best posting hours ---
st.header("Best Posting Hours")
hdf = safe_query_to_df("""
    SELECT CAST(strftime('%H', posted_at) AS INTEGER) as hour,
           AVG(likes) as avg_likes,
           COUNT(*) as tweets
    FROM tweets
    GROUP BY hour
    ORDER BY hour
""")
if hdf is None:
    st.info(":material/inbox: Could not load posting hours data. The table may be missing.")
elif hdf.empty:
    st.info(":material/inbox: No tweet data yet.")
else:
    chart = alt.Chart(hdf).mark_bar().encode(
        x=alt.X("hour:O", title="Hour of Day (UTC)"),
        y="avg_likes:Q",
        color=alt.Color("avg_likes:Q", scale=alt.Scale(scheme="blues")),
        tooltip=["hour", "avg_likes", "tweets"]
    ).properties(height=300)
    st.altair_chart(chart, width='stretch')

# --- Top 5 & Bottom 3 tweets ---
st.header("Top 5 Tweets")
top = safe_query_to_df("SELECT text, likes, impressions FROM tweets ORDER BY likes DESC LIMIT 5")
if top is None:
    st.info(":material/inbox: Could not load top tweets. The table may be missing.")
elif top.empty:
    st.info(":material/inbox: No tweets yet.")
else:
    top["text"] = top["text"].apply(lambda x: (x[:60] + "…") if len(x) > 60 else x)
    st.dataframe(top, width='stretch')

st.header("Bottom 3 Tweets")
bottom = safe_query_to_df("SELECT text, likes, impressions FROM tweets ORDER BY likes ASC LIMIT 3")
if bottom is None:
    st.info(":material/inbox: Could not load bottom tweets. The table may be missing.")
elif bottom.empty:
    st.info(":material/inbox: No tweets yet.")
else:
    bottom["text"] = bottom["text"].apply(lambda x: (x[:60] + "…") if len(x) > 60 else x)
    st.dataframe(bottom, width='stretch')