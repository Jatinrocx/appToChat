"""
🗄️ Database Setup (SQLAlchemy)

This file sets up the database connection using SQLAlchemy ORM.

💡 LEARNING NOTES:
- Engine: The "connection" to the database. Think of it like a database client.
- SessionLocal: A factory that creates database sessions (like opening a transaction).
- Base: All our models (User, Group, Message) inherit from this.
         SQLAlchemy uses it to know which tables to create.
- get_db(): A FastAPI "dependency" — it automatically gives each API request
            its own database session, and closes it when done.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

# ── Create the database engine ──
# connect_args is only needed for SQLite (allows multi-threaded access)
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=settings.DEBUG  # Prints SQL queries to console when DEBUG=True (great for learning!)
)

# ── Session factory ──
# Each API request gets its own session via get_db()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ── Base class for all models ──
Base = declarative_base()


def get_db():
    """
    FastAPI dependency that provides a database session.

    Usage in a route:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            ...

    The session is automatically closed after the request finishes.
    """
    db = SessionLocal()
    try:
        yield db  # Give the session to the route
    finally:
        db.close()  # Always cleanup, even if there's an error
