"""
🚀 Chat App Backend — Main Entry Point

This is where FastAPI starts. It:
1. Creates the app instance
2. Creates all database tables on startup
3. Will eventually mount all routers (auth, groups, messages, websocket)

💡 LEARNING NOTE:
- FastAPI() creates the web server
- @app.on_event("startup") runs code when the server starts
- Base.metadata.create_all() looks at ALL models that inherit from Base
  and creates their tables in the database if they don't exist yet
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, Base

# Import all models so SQLAlchemy knows about them
from app.models import User, Group, GroupMember, Message  # noqa: F401

# ── Create the FastAPI app ──
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Real-time chat backend with WebSockets, RBAC, and file relay",
)

# ── CORS Middleware ──
# Allows the frontend (running on a different port/domain) to talk to our API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    """Create all database tables when the server starts."""
    print("[*] Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("[OK] Database tables ready!")


@app.get("/", tags=["Health"])
def health_check():
    """
    Health check endpoint.
    Hit this to verify the server is running.
    """
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }
