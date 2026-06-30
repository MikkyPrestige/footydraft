"""Database backup: copies SQLite file, compresses it for Dropbox, and uploads to Dropbox + Telegram."""
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



def cleanup_old_dropbox_backups():
    """Delete Dropbox backup files older than 7 days (filename‑based)."""
    import dropbox
    dbx = dropbox.Dropbox(
        oauth2_refresh_token=DROPBOX_REFRESH_TOKEN,
        app_key=DROPBOX_APP_KEY,
        app_secret=DROPBOX_APP_SECRET,
    )
    now_date = datetime.utcnow().date()
    try:
        result = dbx.files_list_folder("/backups", recursive=False)
        files = result.entries
        while result.has_more:
            result = dbx.files_list_folder_continue(result.cursor)
            files.extend(result.entries)
    except dropbox.exceptions.ApiError as e:
        print(f"Dropbox cleanup list failed: {e}")
        return

    for entry in files:
        fname = entry.name
        if not fname.startswith("agent_backup_"):
            continue
        try:
            date_str = fname.split("_")[2]
            file_date = datetime.strptime(date_str, "%Y%m%d").date()
            age_days = (now_date - file_date).days
            if age_days > 7:
                dbx.files_delete_v2(entry.path_lower)
                print(f"Deleted old Dropbox backup: {fname} ({age_days} days old)")
        except (IndexError, ValueError, dropbox.exceptions.ApiError) as e:
            print(f"Dropbox cleanup error for {fname}: {e}")
def daily_backup():
    """Create and upload a database backup. Returns path, or None if locked."""
    global _last_backup_time

    # Atomic file‑based lock (prevents concurrent backups)
    lockfile = os.path.join(BACKUP_DIR, "backup.lock")
    try:
        open(lockfile, "x").close()   # 'x' mode fails if file exists → atomic
    except FileExistsError:
        print("Backup already in progress.")
        return None
    try:
        # Enforce minimum interval
        now = datetime.utcnow()
        if _last_backup_time and (now - _last_backup_time).total_seconds() < MIN_BACKUP_INTERVAL_SECONDS:
            raise RuntimeError("Backup too soon – please wait a minute.")
        _last_backup_time = now

        # Create backup
        path = create_backup()

        # Upload to Dropbox (primary)
        if DROPBOX_REFRESH_TOKEN:
            upload_to_dropbox(path)
            cleanup_old_dropbox_backups()

        # Also send to Telegram (secondary)
        send_backup_to_telegram(path)

        # Remove local backups older than 7 days (filename‑based)
        now_date = datetime.utcnow().date()
        for fname in os.listdir(BACKUP_DIR):
            fpath = os.path.join(BACKUP_DIR, fname)
            if not os.path.isfile(fpath):
                continue
            # Expect filenames like agent_backup_20260629_205125.db or .db.gz
            if not fname.startswith("agent_backup_"):
                continue
            try:
                date_str = fname.split("_")[2]  # YYYYMMDD
                file_date = datetime.strptime(date_str, "%Y%m%d").date()
                age_days = (now_date - file_date).days
                if age_days > 7:
                    os.remove(fpath)
                    print(f"Removed old local backup: {fname} ({age_days} days old)")
            except (IndexError, ValueError):
                continue

        return path
    finally:
        os.remove(lockfile)
