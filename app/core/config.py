from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "development"
    debug: bool = False
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: str = "*"

    database_url: str | None = None
    postgres_db: str | None = None
    postgres_user: str | None = None
    postgres_password: str | None = None
    postgres_host: str | None = None
    postgres_port: int | None = None

    jwt_secret_key: str = "change-this-secret"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 30

    argon2_time_cost: int = 3
    argon2_memory_cost: int = 65536

    otp_expires_seconds: int = 180
    otp_length: int = 6
    otp_attempt_limit: int = 3

    # Verification is part of the OTP architecture but enforcement is
    # behind a flag: OTP delivery and resend are not wired up yet, so
    # requiring verification would lock out every unverified account.
    require_verified_user: bool = False

    # Local LLM (Ollama) assistant configuration.
    ai_enabled: bool = True
    ai_provider: str = "ollama"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2"
    ollama_timeout_seconds: float = 30.0
    ollama_keep_alive: str = "5m"
    ollama_max_attempts: int = 2
    ollama_retry_backoff_seconds: float = 0.25
    ai_temperature: float = 0.3
    ai_max_output_tokens: int = 512
    ai_history_max_messages: int = 10

    # User-scoped assistant context (goals, tasks, workspaces).
    ai_context_enabled: bool = True
    ai_context_max_chars: int = 4000
    ai_context_max_goals: int = 8
    ai_context_max_workspaces: int = 5
    ai_context_max_workspace_tasks: int = 10
    ai_context_max_activity: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
