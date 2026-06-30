#!/bin/bash
# Football Twitter Agent startup

echo "Starting Football Twitter Agent..."

# Remove stale backup lock file (if any)
rm -f /app/data/backups/backup.lock

# Enable swap (256MB) to prevent OOM kills
SWAPFILE=/app/data/swapfile
if [ ! -f "$SWAPFILE" ]; then
    fallocate -l 256M "$SWAPFILE"
    mkswap "$SWAPFILE"
fi
chmod 0600 "$SWAPFILE"
swapon "$SWAPFILE"

# Only clear old event cache > 24h, keep drafts intact
python -c "
from core.database import SessionLocal
from core.models import EventCache
from datetime import datetime, timedelta
s = SessionLocal()
cutoff = datetime.utcnow() - timedelta(hours=24)
s.query(EventCache).filter(EventCache.created_at < cutoff).delete()
s.commit()
print('Stale event cache cleared')
"

# Initialize database (creates tables if missing)
python -c "from core.database import init_db; init_db(); print('Database ready')"


# Startup backup (also runs cleanup)
python -c "
from core.backup import daily_backup
daily_backup()
print('Startup backup created')
"

# Start scheduler in background
python -m core.scheduler &
SCHED_PID=$!
echo "Scheduler started (PID $SCHED_PID)"

# Start Telegram bot in background
python -m bot.main &
BOT_PID=$!
echo "Telegram bot started (PID $BOT_PID)"

# Wait for either process to exit
wait -n $SCHED_PID $BOT_PID

echo "A process exited, shutting down."
kill $SCHED_PID $BOT_PID 2>/dev/null
exit 1
