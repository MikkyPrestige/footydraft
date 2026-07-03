"""Source health monitor: records fetch outcomes and detects failures."""
from datetime import datetime
from sqlalchemy.orm import Session
from core.database import SessionLocal
from core.models import SourceHealth

def record_success(source_name: str):
    """Mark a successful fetch for the given source."""
    with SessionLocal() as session:
        _upsert_health(session, source_name, success=True)

def record_failure(source_name: str):
    """Mark a failed fetch and possibly set status to DOWN."""
    with SessionLocal() as session:
        _upsert_health(session, source_name, success=False)

def _upsert_health(session: Session, name: str, success: bool):
    entry = session.get(SourceHealth, name)
    if not entry:
        entry = SourceHealth(source_name=name)
        session.add(entry)

    now = datetime.utcnow()
    if success:
        entry.last_success = now
        entry.consecutive_failures = 0
        entry.status = "UP"
    else:
        entry.last_failure = now
        entry.consecutive_failures = (entry.consecutive_failures or 0) + 1
        if entry.consecutive_failures >= 3:
            entry.status = "DOWN"
    session.commit()
