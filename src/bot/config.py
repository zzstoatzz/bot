import logging

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra fields from old configs
    )

    # Bluesky credentials
    bluesky_handle: str
    bluesky_password: str
    bluesky_service: str = "https://bsky.social"

    # Bot configuration
    bot_name: str = "Bot"
    personality_file: str = "personalities/phi.md"

    # LLM configuration (support multiple providers)
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    # Google Search configuration
    google_api_key: str | None = None
    google_search_engine_id: str | None = None

    # Server configuration
    host: str = "0.0.0.0"
    port: int = 8000

    # Polling configuration
    notification_poll_interval: int = 10  # seconds (faster for testing)

    # Debug mode
    debug: bool = True  # Default to True for development

    @model_validator(mode="after")
    def configure_logging(self):
        """Configure logging based on debug setting"""
        if self.debug:
            logging.basicConfig(
                level=logging.DEBUG,
                format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%H:%M:%S",
            )
            logging.getLogger("bot").setLevel(logging.DEBUG)
        else:
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s [%(levelname)s] %(message)s",
                datefmt="%H:%M:%S",
            )
        return self


settings = Settings()  # type: ignore[call-arg]
