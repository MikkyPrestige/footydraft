"""Database backup: copies SQLite file and uploads to Dropbox + Telegram."""
import os
import gzip
import shutil
import requests
from datetime import datetime
from config.settings import (
    DATABASE_URL,
    TELEGRAM_BOT_TOKEN,
    ADMIN_CHAT_ID,
    DROPBOX_APP_KEY,
    DROPBOX_APP_SECRET,
    DROPBOX_REFRESH_TOKEN,
)

DB_PATH = DATABASE_URL.replace("sqlite:///", "")
BACKUP_DIR = "data/backups"

_last_backup_time: datetime | None = None
MIN_BACKUP_INTERVAL_SECONDS = 60

def is_backup_allowed() -> bool:
    global _last_backup_time
    now = datetime.utcnow()
    if _last_backup_time and (now - _last_backup_time).total_seconds() < MIN_BACKUP_INTERVAL_SECONDS:
        return False
    _last_backup_time = now
    return True
    return True

def create_backup() -> str:
    """Copy the current database to a timestamped file, return the path."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_name = f"agent_backup_{timestamp}.db"
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    shutil.copy2(DB_PATH, backup_path)
    return backup_path

def send_backup_to_telegram(backup_path: str):
    """Send the backup file to the admin's Telegram chat."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
    with open(backup_path, "rb") as f:
        files = {"document": f}
        data = {"chat_id": ADMIN_CHAT_ID}
        response = requests.post(url, files=files, data=data)
        if response.status_code != 200:
            raise RuntimeError(f"Failed to send backup to Telegram: {response.text}")

def upload_to_dropbox(backup_path: str):
    """Compress the backup and upload to Dropbox (App folder)."""
    import dropbox
    dbx = dropbox.Dropbox(
        oauth2_refresh_token=DROPBOX_REFRESH_TOKEN,
        app_key=DROPBOX_APP_KEY,
        app_secret=DROPBOX_APP_SECRET,
    )
    gz_path = backup_path + ".gz"
    with open(backup_path, "rb") as f_in, gzip.open(gz_path, "wb") as f_out:
        f_out.writelines(f_in)
    dest_path = f"/backups/{os.path.basename(gz_path)}"
    with open(gz_path, "rb") as f:
        dbx.files_upload(f.read(), dest_path, mode=dropbox.files.WriteMode.overwrite)
    os.remove(gz_path)  # cleanup local .gz after upload
    print(f"Uploaded compressed backup to Dropbox: {dest_path}")

def daily_backup():
    """Create and upload a database backup to Dropbox, then also to Telegram."""
    path = create_backup()
    # Upload to Dropbox (primary)
    if DROPBOX_REFRESH_TOKEN:
        upload_to_dropbox(path)
    # Also send to Telegram (secondary)
    send_backup_to_telegram(path)
    # Keep only last 7 local backups
    all_backups = sorted([
        os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR)
    ], key=os.path.getmtime)
    for old in all_backups[:-7]:
        os.remove(old)
    return path
