"""Database engine and session configuration."""
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base


def load_local_env_files() -> None:
    """Load local configuration without replacing variables exported by the shell."""
    app_dir = Path(__file__).resolve().parent
    for env_path in (app_dir / ".env", app_dir.parent / ".env"):
        if not env_path.exists():
            continue
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_local_env_files()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is not set. "
        "Export it before starting FastAPI, or add it to app/.env or the repository-root .env."
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
