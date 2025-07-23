from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from bot.logging_config import setup_logging


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Bluesky credentials
    bluesky_handle: str = Field(..., description="The handle of the Bluesky account")
    bluesky_password: str = Field(
        ..., description="The password of the Bluesky account"
    )
    bluesky_service: str = Field(
        "https://bsky.social", description="The service URL of the Bluesky account"
    )

    # Bot configuration
    bot_name: str = Field("Bot", description="The name of the bot")
    personality_file: str = Field(
        "personalities/phi.md", description="The file containing the bot's personality"
    )

    # LLM configuration (support multiple providers)
    openai_api_key: str | None = Field(
        None, description="The API key for the OpenAI API"
    )
    anthropic_api_key: str | None = Field(
        None, description="The API key for the Anthropic API"
    )

    # Google Search configuration
    google_api_key: str | None = Field(
        None, description="The API key for the Google API"
    )
    google_search_engine_id: str | None = Field(
        None, description="The search engine ID for the Google API"
    )

    # TurboPuffer configuration
    turbopuffer_api_key: str | None = Field(
        None, description="The API key for the TurboPuffer API"
    )
    turbopuffer_namespace: str = Field(
        "bot-memories", description="The namespace for the TurboPuffer API"
    )
    turbopuffer_region: str = Field(
        "gcp-us-central1", description="The region for the TurboPuffer API"
    )

    # Server configuration
    host: str = Field("0.0.0.0", description="The host for the server")
    port: int = Field(8000, description="The port for the server")

    # Polling configuration
    notification_poll_interval: int = Field(
        10, description="The interval for polling for notifications"
    )

    # Debug mode
    debug: bool = Field(True, description="Whether to run in debug mode")

    @model_validator(mode="after")
    def configure_logging(self) -> Self:
        """Configure beautiful logging"""
        setup_logging(debug=self.debug)
        return self


settings = Settings()
