"""Rule Manager – view active/suggested rules and push new ones to the bot."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import streamlit as st
import pandas as pd
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, DatabaseError
from requests.exceptions import ConnectionError, Timeout

from dashboard.utils import restore_backup_state, send_rule_command_to_telegram
from dashboard.ui_components import apply_global_styles, render_sidebar

# Attempt auto‑restore (safe – any errors will be caught below)
try:
    restore_backup_state()
except Exception:
    pass  # We'll handle it in the main flow

st.set_page_config(
    page_title="Rule Manager",
    layout="wide",
    page_icon="dashboard/static/favicon.ico"
)

# Inject global styles and render sidebar
apply_global_styles()
render_sidebar()

st.title(":material/rule: Rule Manager")

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

# Force word‑wrap inside the rules table for mobile
st.markdown(
    """<style>
    .stDataFrame td {
        word-break: break-all;
        overflow-wrap: break-word;
    }
    </style>""",
    unsafe_allow_html=True,
)

# --- Active Rules ---
st.header("Active Rules")
df_active = safe_query_to_df("SELECT rule_text, source, created_at FROM rules WHERE active = 1 ORDER BY created_at DESC")
if df_active is None:
    st.info(":material/inbox: Could not load rules. The table may be missing.")
elif df_active.empty:
    st.info(":material/inbox: No active rules. Add one using the form below.")
else:
    st.dataframe(df_active, width='stretch')

# --- Suggested Rules ---
st.header("Suggested Rules")
df_sug = safe_query_to_df("SELECT id, rule_text, created_at FROM rules WHERE active = 0 AND source = 'auto' ORDER BY created_at DESC")
if df_sug is None:
    st.info(":material/inbox: Could not load suggested rules. The table may be missing.")
elif df_sug.empty:
    st.info(":material/inbox: No suggested rules right now.")
else:
    for _, row in df_sug.iterrows():
        st.write(row["rule_text"])
        if st.button("Send Rule", key=f"send_{row['id']}"):
            try:
                send_rule_command_to_telegram(row["rule_text"])
                st.success(":material/check_circle: Command sent to Telegram. Copy it from there and send it.")
            except ConnectionError:
                st.error(":material/wifi_off: Could not connect to Telegram. Check your internet.")
            except Timeout:
                st.error(":material/timer_off: Telegram request timed out. Try again later.")
            except Exception as e:
                st.error(f":material/error: Failed to send rule: {e}")

# --- Add Manual Rule ---
st.header("Add New Manual Rule")
new_rule = st.text_input("Rule text", placeholder="e.g. Avoid transfer gossip about Club X")
if st.button("Send Rule"):
    if new_rule.strip():
        try:
            send_rule_command_to_telegram(new_rule.strip())
            st.success(":material/check_circle: Command sent to Telegram. Copy it from there and send it.")
        except ConnectionError:
            st.error(":material/wifi_off: Could not connect to Telegram. Check your internet.")
        except Timeout:
            st.error(":material/timer_off: Telegram request timed out. Try again later.")
        except Exception as e:
            st.error(f":material/error: Failed to send rule: {e}")
    else:
        st.warning(":material/warning: Please enter a rule.")