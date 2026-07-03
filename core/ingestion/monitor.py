"""Source health monitor: records fetch outcomes and detects failures."""
from datetime import datetime
from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from core.database import SessionLocal
from core.models import SourceHealth

def _table_exists(session: Session) -> bool:
    """Check if the source_health table exists in the database."""
    try:
        inspector = inspect(session.get_bind())
        return inspector.has_table("source_health")
    except Exception:
        return False

def record_success(source_name: str):
    """Mark a successful fetch for the given source, if table exists."""
    with SessionLocal() as session:
        if not _table_exists(session):
            return  # Table doesn't exist yet — skip
        _upsert_health(session, source_name, success=True)

def record_failure(source_name: str):
    """Mark a failed fetch and possibly set status to DOWN, if table exists."""
    with SessionLocal() as session:
        if not _table_exists(session):
            return  # Table doesn't exist yet — skip
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