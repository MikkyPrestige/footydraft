"""Shared utilities for the Streamlit dashboard."""
import os
import gzip
import tempfile
import streamlit as st
import dropbox
import requests
import pandas as pd
from sqlalchemy import create_engine
from config.settings import (
    DROPBOX_APP_KEY,
    DROPBOX_APP_SECRET,
    DROPBOX_REFRESH_TOKEN,
)

@st.cache_resource
def get_dropbox_client():
    """Return an authenticated Dropbox client (cached)."""
    return dropbox.Dropbox(
        oauth2_refresh_token=DROPBOX_REFRESH_TOKEN,
        app_key=DROPBOX_APP_KEY,
        app_secret=DROPBOX_APP_SECRET,
    )

def download_latest_backup() -> str | None:
    """Download the most recent .db.gz from Dropbox, return local path."""
    dbx = get_dropbox_client()
    try:
        result = dbx.files_list_folder("/backups", recursive=False)
        files = result.entries
        while result.has_more:
            result = dbx.files_list_folder_continue(result.cursor)
            files.extend(result.entries)
    except requests.exceptions.ConnectionError as e:
        raise requests.exceptions.ConnectionError(
            "Could not connect to Dropbox. Please check your internet connection."
        ) from e
    except requests.exceptions.Timeout as e:
        raise requests.exceptions.Timeout(
            "Dropbox request timed out. Please try again."
        ) from e
    except dropbox.exceptions.AuthError as e:
        raise dropbox.exceptions.AuthError(
            "Dropbox token is invalid or expired. Update it in your .env file."
        ) from e
    except Exception as e:
        raise RuntimeError(
            f"An unexpected error occurred while accessing Dropbox: {e}"
        ) from e

    gz_files = [f for f in files if f.name.endswith(".db.gz")]
    if not gz_files:
        st.warning("No backup files found in Dropbox.")
        return None

    # pick newest by filename
    gz_files.sort(key=lambda f: f.name, reverse=True)
    latest = gz_files[0]
    dest = os.path.join(tempfile.gettempdir(), latest.name)

    try:
        dbx.files_download_to_file(dest, latest.path_lower)
    except requests.exceptions.ConnectionError as e:
        raise requests.exceptions.ConnectionError(
            "Could not connect to Dropbox to download the file. Check your internet."
        ) from e
    except requests.exceptions.Timeout as e:
        raise requests.exceptions.Timeout(
            "Dropbox download timed out. Try again."
        ) from e
    except dropbox.exceptions.AuthError as e:
        raise dropbox.exceptions.AuthError(
            "Dropbox token is invalid or expired. Update it in your .env file."
        ) from e
    except Exception as e:
        raise RuntimeError(
            f"Failed to download backup from Dropbox: {e}"
        ) from e

    return dest

def load_database(path: str):
    """Decompress a .db.gz and return a SQLite engine (file‑based)."""
    db_path = path.replace(".gz", "")
    with gzip.open(path, "rb") as f_in, open(db_path, "wb") as f_out:
        f_out.write(f_in.read())
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    return engine

@st.cache_resource(ttl=3600)
def load_latest_backup_engine():
    """Download the latest backup, decompress, and return a SQLite engine (cached)."""
    path = download_latest_backup()
    if not path:
        return None
    return load_database(path)

def restore_backup_state():
    """Auto‑restore the backup engine from cache (survives refreshes)."""
    if not st.session_state.get("backup_loaded"):
        engine = load_latest_backup_engine()
        if engine:
            st.session_state.backup_loaded = True
            st.session_state.db_engine = engine

def push_rule_to_bot(rule_text: str):
    """Send /addrule command to the Telegram bot."""
    import requests
    from config.settings import TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": ADMIN_CHAT_ID,
        "text": f"/addrule {rule_text}",
    })
    if resp.status_code != 200:
        raise RuntimeError(f"Telegram API error: {resp.text}")
    return resp.json()

def send_rule_command_to_telegram(rule_text: str):
    """Send a copy‑instruction message to the Telegram admin chat."""
    import requests
    from config.settings import TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    text = f"Copy and send this command:\n`/addrule {rule_text}`"
    resp = requests.post(url, json={
        "chat_id": ADMIN_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
    })
    if resp.status_code != 200:
        raise RuntimeError(f"Telegram API error: {resp.text}")
    return resp.json()

def send_livecheck_to_telegram():
    """Send /livecheck command to the Telegram bot."""
    import requests
    from config.settings import TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": ADMIN_CHAT_ID,
        "text": "/livecheck",
    })
    if resp.status_code != 200:
        raise RuntimeError(f"Telegram API error: {resp.text}")
    return resp.json()

def send_bot_command(command_text: str):
    """Send a raw command to the Telegram bot (admin chat)."""
    import requests
    from config.settings import TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": ADMIN_CHAT_ID,
        "text": command_text,
    })
    if resp.status_code != 200:
        raise RuntimeError(f"Telegram API error: {resp.text}")
    return resp.json()

def send_draft_command_to_telegram(command: str):
    """Send a copy‑instruction message for a draft command to the Telegram admin chat."""
    import requests
    from config.settings import TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    text = f"Copy and send this command:\n`{command}`"
    resp = requests.post(url, json={
        "chat_id": ADMIN_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
    })
    if resp.status_code != 200:
        raise RuntimeError(f"Telegram API error: {resp.text}")
    return resp.json()

def toggle_xquik_and_restart(enable: bool):
    """Set XQUIK_POSTING_ENABLED secret on Fly.io and restart the machine."""
    import requests
    from config.settings import FLY_API_TOKEN, FLY_APP_NAME, FLY_MACHINE_ID

    if not FLY_API_TOKEN or not FLY_APP_NAME or not FLY_MACHINE_ID:
        raise ValueError("Fly.io credentials not set in environment variables")

    new_value = "1" if enable else "0"

    # 1) Set the secret via Fly REST API (no GraphQL)
    secrets_url = f"https://api.machines.dev/v1/apps/{FLY_APP_NAME}/secrets"
    resp = requests.post(
        secrets_url,
        json={"secrets": [{"key": "XQUIK_POSTING_ENABLED", "value": new_value}]},
        headers={"Authorization": f"Bearer {FLY_API_TOKEN}"},
        timeout=15,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Failed to set secret (status {resp.status_code}): {resp.text}")

    # 2) Restart the machine so the new secret takes effect
    restart_url = f"https://api.machines.dev/v1/apps/{FLY_APP_NAME}/machines/{FLY_MACHINE_ID}/restart"
    resp2 = requests.post(
        restart_url,
        headers={"Authorization": f"Bearer {FLY_API_TOKEN}"},
        timeout=10,
    )
    if resp2.status_code != 200:
        raise RuntimeError(f"Failed to restart machine: {resp2.text}")
