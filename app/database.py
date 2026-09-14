"""File handles connecting to a postgres database"""
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base




def load_env() -> None:
    """Load values from the repository-level .env file if present."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


# Importing ``database`` is part of every route's DB dependency chain, so load
# local secrets before creating the engine/session factory.
load_env()
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is required. Copy .env.example to .env and add your Neon URL."
    )

# SQLlite option for online hosting/production (only if url for sqllite is specified or fallback)
is_sqlite = DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread":False} if is_sqlite else {"connect_timeout":5}

# tells sqlalchemy how to connect to database pool_pre_ping creates new connection after a database is dead.
# Pool_recycle = if connection > 5 minutes, create a fresh connection
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=not is_sqlite, pool_recycle=300)

# enable sqlalchmy to talk to the database
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Parent class to create tables 
Base = declarative_base()


def get_db():
    """Function is crucial for making db queries for routes"""
    db = SessionLocal()
    try:
        yield db 
    finally:
        db.close()
