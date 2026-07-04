from sqlalchemy import Column, Integer, String, DateTime, JSON, Float, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from core.database import Base

class Draft(Base):
    __tablename__ = "drafts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_hash = Column(String(128), nullable=False, index=True)
    content_type = Column(String(32), nullable=False)   # live, normal, analysis
    persona = Column(String(32), nullable=False)        # pundit, fan, analyst
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(32), default="pending")      # pending, pending_live, posted, rejected
    text_variants = Column(JSON, nullable=False)        # list of strings
    selected_variant = Column(Integer, default=None)    # index of chosen variant
    match_confidence = Column(Float, default=None)

    # Relationship: one-to-one with Tweet (Tweet has the FK)
    tweet = relationship("Tweet", back_populates="draft", uselist=False)

class Tweet(Base):
    __tablename__ = "tweets"
    id = Column(String(64), primary_key=True)           # X tweet ID (or URL)
    draft_id = Column(Integer, ForeignKey("drafts.id"), nullable=True, unique=True)
    text = Column(Text, nullable=False)
    posted_at = Column(DateTime, nullable=False)
    likes = Column(Integer, default=0)
    retweets = Column(Integer, default=0)
    replies = Column(Integer, default=0)
    impressions = Column(Integer, default=0)
    last_metrics_fetch = Column(DateTime, default=datetime.utcnow)

    draft = relationship("Draft", back_populates="tweet")

class Rule(Base):
    __tablename__ = "rules"
    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_text = Column(Text, nullable=False)
    source = Column(String(16), default="manual")       # auto or manual
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class SourceHealth(Base):
    __tablename__ = "source_health"
    source_name = Column(String(64), primary_key=True)
    last_success = Column(DateTime, nullable=True)
    last_failure = Column(DateTime, nullable=True)
    consecutive_failures = Column(Integer, default=0)
    status = Column(String(16), default="UP")           # UP or DOWN

class EventCache(Base):
    __tablename__ = "event_cache"
    event_hash = Column(String(128), primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expiry = Column(DateTime, nullable=False)
