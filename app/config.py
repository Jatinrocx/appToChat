"""
⚙️ Application Configuration

This file holds all configurable settings for the app.
In production, these would come from environment variables.
For local dev, we use sensible defaults.

💡 LEARNING NOTE:
- SECRET_KEY is used to sign JWT tokens. Anyone with this key can forge tokens.
- In production, NEVER hardcode secrets — use env vars or a secrets manager.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file (if it exists)
load_dotenv()


class Settings:
    """Central configuration for the entire app."""

    # ── App Info ──
    APP_NAME: str = "Chat App Backend"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"

    # ── Database ──
    # SQLite for local development (creates a file called chat.db)
    # For Supabase deployment, set DATABASE_URL env var to your PostgreSQL URL
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./chat.db"  # Default: SQLite file in project root
    )

    # ── Authentication ──
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super-secret-dev-key-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # ── File Uploads ──
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "uploads")
    MAX_FILE_SIZE_MB: int = 10  # Max 10MB per file
    ALLOWED_FILE_TYPES: dict = {
        "image": [".jpg", ".jpeg", ".png", ".gif", ".webp"],
        "audio": [".mp3", ".wav", ".ogg", ".m4a"],
        "document": [".pdf", ".doc", ".docx", ".txt", ".xlsx", ".csv"],
    }


# Single instance used across the app
settings = Settings()
