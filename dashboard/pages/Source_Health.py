"""Source Health – monitor news feed status."""
import streamlit as st
import pandas as pd
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, DatabaseError

from dashboard.utils import restore_backup_state
from dashboard.ui_components import apply_global_styles, render_sidebar

# Attempt auto‑restore (safe – any errors will be caught below)
try:
    restore_backup_state()
except Exception:
    pass  # We'll handle it in the main flow

st.set_page_config(
    page_title="Source Health",
    layout="wide",
    page_icon="dashboard/static/favicon.ico"
)

# Inject global styles and render sidebar
apply_global_styles()
render_sidebar()

st.title(":material/satellite_alt: Source Health")

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

# Force word‑wrap inside the source health table for mobile
st.markdown(
    """<style>
    .stDataFrame td {
        word-break: break-all;
        overflow-wrap: break-word;
    }
    </style>""",
    unsafe_allow_html=True,
)

# --- Main query ---
df = safe_query_to_df("""
    SELECT source_name, status, last_success, last_failure, consecutive_failures
    FROM source_health
    ORDER BY status DESC, consecutive_failures DESC
""")

if df is None:
    st.info(":material/inbox: Could not load source health data. The table may be missing.")
    st.stop()

if df.empty:
    st.info(":material/inbox: No source health data yet.")
    st.stop()

# Truncate datetime columns to time only for mobile display
for col in ("last_success", "last_failure"):
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce")
        df[col] = df[col].apply(lambda x: x.strftime("%H:%M:%S") if not pd.isna(x) else "—")

# Color coding
def color_status(val):
    if val == "UP":
        return "background-color: #d4edda; color: #155724"
    elif val == "DOWN":
        return "background-color: #f8d7da; color: #721c24"
    return ""

styled = df.style.map(color_status, subset=["status"])
st.dataframe(styled, width='stretch')

# --- Summary cards (dark gradient theme) ---
up = (df["status"] == "UP").sum()
down = (df["status"] == "DOWN").sum()

summary_html = (
    '<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin-top: 1rem;">'
    '<div style="background: linear-gradient(135deg, #1e1e2f 0%, #2a2a3e 100%); border: 1px solid #3a3a4e; border-radius: 14px; padding: 1.5rem; box-shadow: 0 2px 8px rgba(0,0,0,0.2);">'
    '<div style="font-size: 0.8rem; color: #888; text-transform: uppercase; letter-spacing: 0.5px;">Sources UP</div>'
    '<div style="font-size: 2rem; font-weight: 700; color: #69f0ae;">' + str(up) + '</div>'
    '</div>'
    '<div style="background: linear-gradient(135deg, #1e1e2f 0%, #2a2a3e 100%); border: 1px solid #3a3a4e; border-radius: 14px; padding: 1.5rem; box-shadow: 0 2px 8px rgba(0,0,0,0.2);">'
    '<div style="font-size: 0.8rem; color: #888; text-transform: uppercase; letter-spacing: 0.5px;">Sources DOWN</div>'
    '<div style="font-size: 2rem; font-weight: 700; color: #ff8a80;">' + str(down) + '</div>'
    '</div>'
    '</div>'
)
st.markdown(summary_html, unsafe_allow_html=True)