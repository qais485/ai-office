import os
import secrets
import logging
from typing import List
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Virtual Office Platform"
    VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"

    # Environment
    ENVIRONMENT: str = "development"

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/ai_office"
    DATABASE_POOL_SIZE: int = 15               # 3 agent loops + scheduler jobs + HTTP requests need headroom
    DATABASE_MAX_OVERFLOW: int = 25            # burst capacity: Neon pooler supports many more
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_POOL_RECYCLE: int = 300           # 5 min: matches Neon pooler idle timeout

    # Security
    SECRET_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ALGORITHM: str = "HS256"

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_OAUTH_REDIRECT_URI: str = ""

    # LLM Configuration
    LLM_PROVIDER: str = "openai"
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_MAX_TOKENS: int = 400                      # Cap on LLM output (agent decisions are small JSON; drafts are short replies)
    LLM_SKIP_AUTOMATED_SENDERS: bool = True        # Skip LLM calls for noreply/notification senders entirely
    LLM_EMAIL_BODY_MAX_CHARS: int = 1000           # Max email body chars sent to the LLM (agent trigger path)
    MIN_SCHEDULED_INTERVAL_SECONDS: int = 300      # Floor for scheduled-trigger intervals (each run = 1 LLM call)

    # Encryption
    ENCRYPTION_KEY: str = ""

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60

    # Embedding Configuration
    EMBEDDING_PROVIDER: str = "openai"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 1536
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_BASE_URL: str = "https://api.openai.com/v1"
    EMBEDDING_BATCH_SIZE: int = 20
    EMBEDDING_MAX_RETRIES: int = 3
    EMBEDDING_RETRY_DELAY: float = 1.0

    # RAG Configuration
    RAG_CHUNK_SIZE: int = 500
    RAG_CHUNK_OVERLAP: int = 100
    RAG_DEFAULT_TOP_K: int = 5
    RAG_SIMILARITY_THRESHOLD: float = 0.3

    # Frontend
    FRONTEND_URL: str = "http://localhost:5173"

    # Integration Config
    TELEGRAM_BOT_TOKEN: str = ""
    SLACK_CLIENT_ID: str = ""
    SLACK_CLIENT_SECRET: str = ""
    DISCORD_CLIENT_SECRET: str = ""
    INSTAGRAM_CLIENT_ID: str = ""
    INSTAGRAM_CLIENT_SECRET: str = ""
    NOTION_API_KEY: str = ""
    CRM_API_KEY: str = ""
    GOOGLE_DRIVE_CLIENT_SECRET: str = ""

    # Scheduler Configuration
    SCHEDULER_TICK_INTERVAL: int = 5               # seconds between scheduler ticks
    EMAIL_POLL_INTERVAL: int = 60                   # seconds between email polling cycles
    GMAIL_POLL_INTERVAL: int = 60                   # seconds between Gmail API checks (1 min)
    TELEGRAM_POLL_INTERVAL: int = 60                # seconds between Telegram account checks (1 min)
    TELEGRAM_WATCH_GROUPS: bool = False             # also watch Telegram groups (default: private chats only)
    TELEGRAM_FETCH_LIMIT: int = 20                  # messages fetched per dialog per cycle
    TELEGRAM_MAX_TRIGGERS_PER_CYCLE: int = 10       # flood cap for agent triggers per account per cycle
    TELEGRAM_BOT_POLL_INTERVAL: int = 60            # seconds between Telegram Bot getUpdates cycles (1 min)
    TELEGRAM_BOT_FETCH_LIMIT: int = 20              # updates fetched per bot per cycle
    TELEGRAM_BOT_MAX_TRIGGERS_PER_CYCLE: int = 10   # flood cap for bot agent triggers per account per cycle
    AGENT_TRIGGER_WORKER_INTERVAL: int = 10         # seconds between scheduled-trigger scans
    AGENT_LOOP_INTERVAL: int = 2                    # seconds between per-agent trigger polls

    # Gmail Push Notifications (Cloud Pub/Sub)
    GMAIL_PUSH_ENABLED: bool = False                # Enable Gmail push notifications
    GCP_PROJECT_ID: str = ""                        # Google Cloud project ID
    GCS_PUBSUB_TOPIC: str = "gmail-notifications"   # Pub/Sub topic name
    GCS_PUBSUB_SUBSCRIPTION: str = "gmail-notifications-sub"  # Pub/Sub subscription name
    GMAIL_WEBHOOK_SECRET: str = ""                  # Shared secret for validating push messages
    GMAIL_WATCH_RENEWAL_INTERVAL: int = 21600       # seconds between watch renewal checks (6 hours)

    class Config:
        case_sensitive = True
        env_file = ".env"

    def model_post_init(self, __context) -> None:
        is_production = self.ENVIRONMENT == "production"

        # SECRET_KEY validation
        if not self.SECRET_KEY or self.SECRET_KEY == "your-secret-key-change-in-production":
            if is_production:
                raise ValueError(
                    "SECRET_KEY must be set to a secure random value in production. "
                    "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
                )
            else:
                self.SECRET_KEY = secrets.token_urlsafe(64)
                logger.warning(
                    "SECRET_KEY not set — using auto-generated key. "
                    "This is INSECURE for production. Set SECRET_KEY in .env"
                )

        # ENCRYPTION_KEY validation
        if not self.ENCRYPTION_KEY:
            if is_production:
                raise ValueError("ENCRYPTION_KEY must be set in production.")
            else:
                self.ENCRYPTION_KEY = secrets.token_urlsafe(32)
                logger.warning("ENCRYPTION_KEY not set — using auto-generated key.")

        # CORS: always include FRONTEND_URL
        if self.FRONTEND_URL and self.FRONTEND_URL not in self.BACKEND_CORS_ORIGINS:
            self.BACKEND_CORS_ORIGINS.append(self.FRONTEND_URL)

        # Database URL validation
        if is_production and "localhost" in self.DATABASE_URL:
            raise ValueError("DATABASE_URL must not point to localhost in production.")

        # LLM API key validation
        if is_production and not self.LLM_API_KEY:
            raise ValueError("LLM_API_KEY must be set in production.")


settings = Settings()
