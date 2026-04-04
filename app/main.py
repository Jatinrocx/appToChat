"""
Chat App Backend — Main Entry Point

Wires together all routers, middleware, and startup logic.
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.config import settings
from app.database import engine, Base

# Import all models so SQLAlchemy knows about them
from app.models import User, Group, GroupMember, Message  # noqa: F401

# Import routers
from app.routers import auth, groups, messages
from app.websocket import handler as ws_handler

# Create the FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Real-time chat backend with WebSockets, RBAC, and file relay. "
                "Built with FastAPI for a chat interface system assignment.",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(auth.router)
app.include_router(groups.router)
app.include_router(ws_handler.router)
app.include_router(messages.router)

# Create upload directories
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
for subdir in ["image", "audio", "document"]:
    os.makedirs(os.path.join(settings.UPLOAD_DIR, subdir), exist_ok=True)

# Serve uploaded files
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")


@app.on_event("startup")
def on_startup():
    """Create all database tables when the server starts."""
    print("[*] Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("[OK] Database tables ready!")
    print(f"[OK] Swagger docs at http://localhost:8000/docs")


@app.get("/", tags=["Health"])
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


# Serve the frontend test page
@app.get("/chat", tags=["Frontend"], include_in_schema=False)
def serve_chat():
    """Serve the chat test page."""
    return FileResponse("static/index.html")
