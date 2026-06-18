import os

from sqlalchemy import create_engine, Column, Integer, String
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

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///matchmind.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
