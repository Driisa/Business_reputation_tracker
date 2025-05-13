"""
Object store database initialization module.
Handles the setup and configuration of the object store database (object_store.db).
This database stores the pipeline's search results, scraped content, and analysis data.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from data.pipeline_db_models import Base

# SQLite will create object_store.db in your working dir
SQLITE_URL = "sqlite:///data/database/object_store.db"

engine = create_engine(
    SQLITE_URL, 
    connect_args={"check_same_thread": False},  # for SQLite + threads
    echo=False
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def drop_all_tables():
    """Drop all tables in the database."""
    Base.metadata.drop_all(bind=engine)

def init_db():
    """Create all tables in the database if they don't exist."""
    # Create tables only if they don't exist
    Base.metadata.create_all(bind=engine)

