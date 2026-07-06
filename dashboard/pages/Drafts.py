"""Drafts & Queue – view all generated drafts with status filters and pagination."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import streamlit as st
import pandas as pd
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, DatabaseError

from dashboard.utils import restore_backup_state, send_draft_command_to_telegram
from dashboard.ui_components import apply_global_styles, render_sidebar, require_auth
from config.settings import XQUIK_POSTING_ENABLED

# Attempt auto‑restore (safe – any errors will be caught below)
try:
    restore_backup_state()
except Exception:
    pass  # handled in the main flow

st.set_page_config(
    page_title="Drafts & Queue",
    layout="wide",
    page_icon="dashboard/static/favicon.ico"
)

# Inject global styles, render sidebar and authentication check
apply_global_styles()
render_sidebar()
require_auth()

# Remove red border from the status filter
st.markdown("""
<style>
div[data-baseweb="select"] > div {
    border-color: #ccc !important;
}
</style>
""", unsafe_allow_html=True)
st.title(":material/newspaper: Drafts & Queue")

# --- Check if backup is loaded ---
if not st.session_state.get("backup_loaded"):
    st.warning(":material/folder_open: No backup loaded. Use the sidebar to load a backup first.")
    st.stop()

engine = st.session_state.db_engine

# --- Validate engine ---
if engine is None:
    st.error(":material/folder_open: Database engine not available. Please reload your backup from the sidebar.")
    st.stop()

# Filter with persistent key and change detection
status_filter = st.selectbox(
    "Filter by status",
    ["all", "pending", "pending_live", "held", "posted"],
    key="drafts_status_filter"
)

if "prev_status_filter" not in st.session_state:
    st.session_state.prev_status_filter = status_filter
elif st.session_state.prev_status_filter != status_filter:
    st.session_state.prev_status_filter = status_filter
    st.session_state.drafts_page = 0
    st.rerun()

# Pagination state
if "drafts_page" not in st.session_state:
    st.session_state.drafts_page = 0

# Read page number from URL (no clearing)
if "page" in st.query_params:
    try:
        st.session_state.drafts_page = int(st.query_params["page"])
    except ValueError:
        pass

page_size = 10
offset = st.session_state.drafts_page * page_size

# --- Total count for the current filter ---
count_query = "SELECT COUNT(*) as cnt FROM drafts"
if status_filter != "all":
    count_query += f" WHERE status = '{status_filter}'"

try:
    with engine.connect() as conn:
        total = pd.read_sql(text(count_query), conn)["cnt"].iloc[0]
except (OperationalError, DatabaseError):
    st.error(":material/inbox: Drafts table not found. Your backup may not contain any drafts yet.")
    st.stop()
except Exception as e:
    st.error(f":material/error: Failed to load draft count: {e}")
    st.stop()

# --- Main query ---
query = "SELECT id, content_type, persona, status, created_at, text_variants FROM drafts"
if status_filter != "all":
    query += f" WHERE status = '{status_filter}'"
query += f" ORDER BY created_at DESC LIMIT {page_size} OFFSET {offset}"

try:
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn)
except (OperationalError, DatabaseError):
    st.error(":material/inbox: Could not load drafts. The drafts table may be missing from your backup.")
    st.stop()
except Exception as e:
    st.error(f":material/error: Failed to load drafts: {e}")
    st.stop()

# --- Display results ---
if df.empty and offset == 0:
    st.info(f":material/inbox: No drafts found for status '{status_filter}'.")
    st.stop()

if df.empty:
    st.info(":material/inbox: No more drafts.")
    if st.button("Previous page"):
        st.session_state.drafts_page = max(0, st.session_state.drafts_page - 1)
        st.rerun()
    st.stop()

for _, row in df.iterrows():
    with st.expander(f"#{row['id']} – {row['persona']} ({row['status']}) – {row['created_at']}"):
        variants = row["text_variants"]
        if isinstance(variants, str):
            import json
            try:
                variants = json.loads(variants)
            except json.JSONDecodeError:
                variants = [variants]
        if variants:
            for i, v in enumerate(variants, 1):
                st.markdown(
                    f"<div style='max-width:100%; word-wrap:break-word; white-space:pre-wrap; background-color:#f0f2f6; padding:0.5rem; border-radius:0.3rem; font-family:monospace; color:#1e1e1e;'>"
                    f"{v}"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                st.button(f"Copy V{i}", key=f"copy_{row['id']}_{i}")
        else:
            st.write("No text variants.")
        # Queue action buttons
        status = row["status"]
        draft_id = row["id"]
        if status in ("pending", "pending_live"):
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("Hold", key=f"hold_{draft_id}"):
                    try:
                        send_draft_command_to_telegram(f"/hold {draft_id}")
                        st.success(f"Held draft #{draft_id}.")
                    except Exception as e:
                        st.error(f"Failed: {e}")
            with col2:
                if st.button("Post (Manual)", key=f"post_{draft_id}"):
                    try:
                        send_draft_command_to_telegram(f"/posted {draft_id}")
                        st.success(f"Posted draft #{draft_id} (manual).")
                    except Exception as e:
                        st.error(f"Failed: {e}")
            with col3:
                if XQUIK_POSTING_ENABLED:
                    if st.button("Post (Xquik)", key=f"postx_{draft_id}"):
                        try:
                            send_draft_command_to_telegram(f"/postx {draft_id} 1")
                            st.success(f"Posted draft #{draft_id} variant 1 via Xquik.")
                        except Exception as e:
                            st.error(f"Failed: {e}")
                else:
                    st.caption("Xquik not enabled")
        elif status == "held":
            if st.button("Release", key=f"release_{draft_id}"):
                try:
                    send_draft_command_to_telegram(f"/release {draft_id}")
                    st.success(f"Released draft #{draft_id}.")
                except Exception as e:
                    st.error(f"Failed: {e}")

# --- Pagination ---
if total > page_size:
    prev_page = max(0, st.session_state.drafts_page - 1)
    next_page = st.session_state.drafts_page + 1
    prev_disabled = "disabled" if st.session_state.drafts_page == 0 else ""
    next_disabled = "disabled" if offset + page_size >= total else ""
    prev_style = "min-width: 110px; cursor: " + ("not-allowed" if prev_disabled else "pointer") + ";"
    next_style = "min-width: 110px; cursor: " + ("not-allowed" if next_disabled else "pointer") + ";"

    table_html = (
        '<div style="overflow-x: auto;">'
        '<table style="border-collapse: collapse;"><tr>'
        '<td style="padding-right: 8px;">'
        '<a href="?page=' + str(prev_page) + '" target="_self">'
        '<button ' + prev_disabled + ' style="' + prev_style + '">← Prev</button>'
        '</a>'
        '</td>'
        '<td>'
        '<a href="?page=' + str(next_page) + '" target="_self">'
        '<button ' + next_disabled + ' style="' + next_style + '">Next →</button>'
        '</a>'
        '</td>'
        '</tr></table>'
        '</div>'
    )
    st.markdown(table_html, unsafe_allow_html=True)