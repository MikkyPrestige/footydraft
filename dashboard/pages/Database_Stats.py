"""Database Stats – quick health overview with HTML cards."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import streamlit as st
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, DatabaseError

from dashboard.utils import restore_backup_state
from dashboard.ui_components import apply_global_styles, render_sidebar

# Attempt auto‑restore (safe – any errors will be caught below)
try:
    restore_backup_state()
except Exception:
    pass  # handled in the main flow

st.set_page_config(
    page_title="Database Stats",
    layout="wide",
    page_icon="dashboard/static/favicon.ico"
)

# Inject global styles and render sidebar
apply_global_styles()
render_sidebar()

# Local card styling for stats
st.markdown("""
<style>
.stat-cards-container {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 1rem;
    margin-top: 1rem;
}
.stat-card {
    background: linear-gradient(135deg, #1e1e2f 0%, #2a2a3e 100%);
    border: 1px solid #3a3a4e;
    border-radius: 14px;
    padding: 1.5rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    transition: all 0.2s ease;
}
.stat-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 16px rgba(0,0,0,0.3);
    border-color: #5a5a7a;
}
.stat-card h3 {
    margin: 0 0 1rem 0;
    font-size: 1.05rem;
    color: #ffffff;
}
.stat-metrics {
    display: flex;
    flex-wrap: wrap;
    gap: 1.5rem;
}
.stat-metric {
    display: flex;
    flex-direction: column;
}
.stat-value {
    font-size: 2rem;
    font-weight: 700;
    color: #e0e0ff;
}
.stat-label {
    font-size: 0.75rem;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.stat-empty {
    color: #888;
    font-size: 0.9rem;
    padding: 0.5rem 0;
}
</style>
""", unsafe_allow_html=True)

st.title(":material/database: Database Stats")

# --- Check if backup is loaded ---
if not st.session_state.get("backup_loaded"):
    st.warning(":material/folder_open: No backup loaded. Use the sidebar to load a backup first.")
    st.stop()

engine = st.session_state.db_engine

# --- Validate engine ---
if engine is None:
    st.error(":material/folder_open: Database engine not available. Please reload your backup from the sidebar.")
    st.stop()

# --- Helper: fetch a scalar safely ---
def safe_scalar(query: str, default=0):
    """Execute a query that returns a single value; return default on error."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text(query)).scalar()
            return result if result is not None else default
    except (OperationalError, DatabaseError):
        return None
    except Exception:
        return None

# --- Helper: fetch rows safely ---
def safe_fetch(query: str):
    """Execute a query that returns rows; return None on error."""
    try:
        with engine.connect() as conn:
            return conn.execute(text(query)).fetchall()
    except (OperationalError, DatabaseError):
        return None
    except Exception:
        return None

# --- Query data (each independently) ---

# Drafts
draft_counts = safe_fetch("""
    SELECT status, COUNT(*) as cnt
    FROM drafts
    GROUP BY status
    ORDER BY cnt DESC
""")

# Tweets
tweet_cnt = safe_scalar("SELECT COUNT(*) as cnt FROM tweets")

# Rules
rule_rows = safe_fetch("""
    SELECT active, COUNT(*) as cnt
    FROM rules
    GROUP BY active
""")
active_rules = 0
inactive_rules = 0
if rule_rows is not None:
    for active, cnt in rule_rows:
        if active:
            active_rules = cnt
        else:
            inactive_rules = cnt

# Sources
source_cnt = safe_scalar("SELECT COUNT(*) as cnt FROM source_health")

# --- Build HTML cards ---
def metric_html(label, value):
    return f'<div class="stat-metric"><div class="stat-value">{value}</div><div class="stat-label">{label}</div></div>'

def empty_metric():
    return f'<div class="stat-empty"><span class="material-symbols-outlined" style="font-size: 1.2rem; vertical-align: middle;">inbox</span> No data available</div>'

cards_html = '<div class="stat-cards-container">'

# Drafts card
if draft_counts is not None:
    drafts_metrics = '<div class="stat-metrics">'
    for status, cnt in draft_counts:
        drafts_metrics += metric_html(status.replace("_", " ").title(), cnt)
    drafts_metrics += '</div>'
    cards_html += f'<div class="stat-card"><h3><span class="material-symbols-outlined" style="font-size: 1.2rem; vertical-align: middle;">description</span> Draft Counts</h3>{drafts_metrics}</div>'
else:
    cards_html += f'<div class="stat-card"><h3><span class="material-symbols-outlined" style="font-size: 1.2rem; vertical-align: middle;">description</span> Draft Counts</h3>{empty_metric()}</div>'

# Tweets card
if tweet_cnt is not None:
    cards_html += f'<div class="stat-card"><h3><span class="material-symbols-outlined" style="font-size: 1.2rem; vertical-align: middle;">chat</span> Tweets</h3><div class="stat-metrics">{metric_html("Total Tweets", tweet_cnt)}</div></div>'
else:
    cards_html += f'<div class="stat-card"><h3><span class="material-symbols-outlined" style="font-size: 1.2rem; vertical-align: middle;">chat</span> Tweets</h3>{empty_metric()}</div>'

# Rules card
if rule_rows is not None:
    rules_metrics = '<div class="stat-metrics">' + metric_html("Active Rules", active_rules) + metric_html("Suggested Rules", inactive_rules) + '</div>'
    cards_html += f'<div class="stat-card"><h3><span class="material-symbols-outlined" style="font-size: 1.2rem; vertical-align: middle;">rule</span> Rules</h3>{rules_metrics}</div>'
else:
    cards_html += f'<div class="stat-card"><h3><span class="material-symbols-outlined" style="font-size: 1.2rem; vertical-align: middle;">rule</span> Rules</h3>{empty_metric()}</div>'

# Sources card
if source_cnt is not None:
    cards_html += f'<div class="stat-card"><h3><span class="material-symbols-outlined" style="font-size: 1.2rem; vertical-align: middle;">satellite_alt</span> News Sources</h3><div class="stat-metrics">{metric_html("Total Sources", source_cnt)}</div></div>'
else:
    cards_html += f'<div class="stat-card"><h3><span class="material-symbols-outlined" style="font-size: 1.2rem; vertical-align: middle;">satellite_alt</span> News Sources</h3>{empty_metric()}</div>'

cards_html += '</div>'

st.markdown(cards_html, unsafe_allow_html=True)