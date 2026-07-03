"""Backup Browser – browse, download, and load backups from Dropbox."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import os
import tempfile
import streamlit as st
import pandas as pd
import dropbox
from requests.exceptions import ConnectionError, Timeout
from sqlalchemy.exc import OperationalError, DatabaseError

from dashboard.utils import restore_backup_state, get_dropbox_client, load_database
from dashboard.ui_components import apply_global_styles, render_sidebar

# Attempt auto‑restore (safe – any errors will be caught below)
try:
    restore_backup_state()
except Exception:
    pass  # handled in the main flow

st.set_page_config(
    page_title="Backup Browser",
    layout="wide",
    page_icon="dashboard/static/favicon.ico"
)

# Inject global styles and render sidebar
apply_global_styles()
render_sidebar()

st.title(":material/folder_open: Backup Browser")

# --- Dropbox client and file listing with error handling ---
try:
    dbx = get_dropbox_client()
    try:
        result = dbx.files_list_folder("/backups", recursive=False)
        files = result.entries
        while result.has_more:
            result = dbx.files_list_folder_continue(result.cursor)
            files.extend(result.entries)
    except ConnectionError:
        st.error(":material/wifi_off: Could not connect to Dropbox. Please check your internet connection and try again.")
        st.stop()
    except Timeout:
        st.error(":material/timer_off: Dropbox request timed out. Please try again later.")
        st.stop()
    except dropbox.exceptions.AuthError:
        st.error(":material/key_off: Dropbox token is invalid or expired. Please update it in your .env file.")
        st.stop()
    except Exception as e:
        st.error(f":material/error: An unexpected error occurred while listing backups: {e}")
        st.stop()

except ConnectionError:
    st.error(":material/wifi_off: Could not reach Dropbox. Check your internet connection.")
    st.stop()
except dropbox.exceptions.AuthError:
    st.error(":material/key_off: Dropbox token is invalid or expired. Update your .env file.")
    st.stop()
except Exception as e:
    st.error(f":material/error: Failed to authenticate with Dropbox: {e}")
    st.stop()

# --- Process the files ---
gz_files = [f for f in files if f.name.endswith(".db.gz")]
if not gz_files:
    st.info(":material/folder_open: No backup files found in Dropbox.")
    st.stop()

# Build a dataframe
rows = []
for f in gz_files:
    size_kb = round(f.size / 1024, 1)
    try:
        date_str = f.name.split("_")[2]  # YYYYMMDD
        backup_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    except (IndexError, ValueError):
        backup_date = "Unknown"
    rows.append({"Filename": f.name, "Date": backup_date, "Size (KB)": size_kb, "Download": f.path_lower})

df = pd.DataFrame(rows).sort_values("Date", ascending=False)

st.dataframe(df[["Filename", "Date", "Size (KB)"]], width='stretch')

# Force word‑wrap inside the backup table for mobile
st.markdown(
    """<style>
    .stDataFrame td {
        word-break: break-all;
        overflow-wrap: break-word;
    }
    </style>""",
    unsafe_allow_html=True,
)

# --- Load or download a selected backup ---
st.header("Load or download a backup")
selected = st.selectbox("Choose a backup file", df["Filename"].tolist())

col1, col2 = st.columns(2)

with col1:
    if st.button("Load into Analytics"):
        try:
            dest = os.path.join(tempfile.gettempdir(), selected)
            dbx.files_download_to_file(dest, f"/backups/{selected}")
            engine = load_database(dest)
            st.session_state.db_engine = engine
            st.session_state.backup_loaded = True
            st.success(f":material/check_circle: Loaded {selected} into analytics.")
        except ConnectionError:
            st.error(":material/wifi_off: Could not connect to Dropbox to download the file. Check your internet.")
        except Timeout:
            st.error(":material/timer_off: Download timed out. Try again later.")
        except dropbox.exceptions.AuthError:
            st.error(":material/key_off: Dropbox token is invalid or expired. Update your .env file.")
        except OperationalError:
            st.error(":material/folder_open: Failed to read the backup file. It may be corrupted or in an invalid format. Try a different backup.")
        except DatabaseError:
            st.error(":material/folder_open: Database error while loading the backup. The file may be incomplete.")
        except Exception as e:
            st.error(f":material/error: Failed to load backup: {e}")

with col2:
    if st.button("Download"):
        try:
            dest = os.path.join(tempfile.gettempdir(), selected)
            dbx.files_download_to_file(dest, f"/backups/{selected}")
            with open(dest, "rb") as f:
                st.download_button("Download file", f, file_name=selected)
        except ConnectionError:
            st.error(":material/wifi_off: Could not connect to Dropbox to download. Check your internet.")
        except Timeout:
            st.error(":material/timer_off: Download timed out. Try again later.")
        except dropbox.exceptions.AuthError:
            st.error(":material/key_off: Dropbox token is invalid or expired. Update your .env file.")
        except Exception as e:
            st.error(f":material/error: Failed to download backup: {e}")