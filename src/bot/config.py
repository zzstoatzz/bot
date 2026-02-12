from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from bot.logging_config import setup_logging


class LogfireSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LOGFIRE_", extra="ignore", env_file=".env")

    token: str | None = None
    environment: str | None = None
    send_to_logfire: Literal["if-token-present"] | None = "if-token-present"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Bluesky credentials
    bluesky_handle: str = Field(
        default=..., description="The handle of the Bluesky account"
    )
    bluesky_password: str = Field(
        default=..., description="The password of the Bluesky account"
    )
    bluesky_service: str = Field(
        default="https://bsky.social",
        description="The service URL of the Bluesky account",
    )

    # Bot configuration
    bot_name: str = Field(default="Bot", description="The name of the bot")
    personality_file: str = Field(
        default="personalities/phi.md",
        description="The file containing the bot's personality",
    )

    # LLM configuration (support multiple providers)
    openai_api_key: str | None = Field(
        default=None, description="The API key for the OpenAI API"
    )
    anthropic_api_key: str | None = Field(
        default=None, description="The API key for the Anthropic API"
    )

    # Google Search configuration
    google_api_key: str | None = Field(
        default=None, description="The API key for the Google API"
    )
    google_search_engine_id: str | None = Field(
        default=None, description="The search engine ID for the Google API"
    )

    # TurboPuffer configuration
    turbopuffer_api_key: str | None = Field(
        default=None, description="The API key for the TurboPuffer API"
    )
    turbopuffer_namespace: str = Field(
        default="bot-memories", description="The namespace for the TurboPuffer API"
    )
    turbopuffer_region: str = Field(
        default="gcp-us-central1", description="The region for the TurboPuffer API"
    )

    # Extraction model for observation extraction
    extraction_model: str = Field(
        default="claude-haiku-4-5-20251001",
        description="Model for extracting observations from conversations",
    )

    # Server configuration
    host: str = Field(default="0.0.0.0", description="The host for the server")
    port: int = Field(default=8000, description="The port for the server")

    # Polling configuration
    notification_poll_interval: int = Field(
        default=10, description="The interval for polling for notifications"
    )

    # Debug mode
    debug: bool = Field(default=True, description="Whether to run in debug mode")

    # Logfire
    logfire: LogfireSettings = Field(default_factory=LogfireSettings)

    @model_validator(mode="after")
    def configure_logging(self) -> Self:
        """Configure stdlib logging."""
        setup_logging(debug=self.debug)
        return self


settings = Settings()
