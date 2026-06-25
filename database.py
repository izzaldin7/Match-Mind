import os
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


class Match(Base):
    __tablename__ = "matches"
    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, unique=True)
    home_team = Column(String)
    away_team = Column(String)
    match_date = Column(String)
    status = Column(String)
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    stage = Column(String)
    group_name = Column(String, nullable=True)
    kick_off_time = Column(String, nullable=True)


class GeneratedContent(Base):
    """
    Persists generated briefing/report text per match so repeated requests
    for the same match don't re-call Groq (or re-fetch Highlightly data)
    after a server restart. One row per (match_id, content_type) pair —
    save_cached_content() in utils.py deletes any prior row before inserting.
    """
    __tablename__ = "generated_content"
    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, index=True)
    content_type = Column(String)   # "report", "briefing", "lineup", "box_score", "match_detail"
    payload = Column(Text)          # JSON-encoded response dict
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///matchmind.db")
# Railway (and some other providers) hand out the legacy "postgres://" scheme,
# which SQLAlchemy 1.4+ rejects outright. Normalize it.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
