from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from bot.logging_config import setup_logging


class LogfireSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LOGFIRE_", extra="ignore", env_file=".env"
    )

    write_token: str | None = None
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
    skills_dir: str = Field(
        default="skills",
        description="Directory containing agentskills.io-format skill packages",
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

    # Tavily web search — grounds phi against the open web for currency
    # checks and source-finding. Free tier covers 1k searches/month.
    tavily_api_key: str | None = Field(
        default=None, description="API key for Tavily web search"
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

    # Model configuration
    agent_model: str = Field(
        default="anthropic:claude-sonnet-4-6",
        description="Model for the main agent (pydantic-ai model string)",
    )
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

    # Daily reflection
    daily_reflection_hour: int = Field(
        default=14, description="UTC hour to post daily reflection (14 = ~9am CT)"
    )

    # Original thought posts
    thought_post_hours: list[int] = Field(
        default=[13, 15, 17, 19, 21, 23, 1, 3],
        description="UTC hours to attempt original thought posts (~8am-10pm CT, every 2h)",
    )

    # Event-driven exploration
    saved_feeds: dict[str, str] = Field(
        default={
            "for-you": "at://did:plc:3guzzweuqraryl3rdkimjamk/app.bsky.feed.generator/for-you",
        },
        description="friendly name → AT-URI for external feeds phi can read",
    )
    # Control API
    control_token: str | None = Field(
        default=None, description="Bearer token for /api/control endpoints"
    )

    # Owner identity (for permission-gated tools)
    owner_handle: str = Field(
        default="zzstoatzz.io",
        description="Handle of the bot's owner (for permission-gated tools)",
    )

    # Relay fleet monitoring — phi polls relay-eval on a schedule and
    # reports status transitions. The service is the source of truth;
    # phi is the courier. This is the base URL; /history and /events
    # are derived from it.
    relays_url: str = Field(
        default="https://relay-eval.waow.tech/api/relays",
        description="Base URL for relay-eval's relay API (snapshot endpoint)",
    )
    relay_check_interval_polls: int = Field(
        default=1080,  # 1080 polls * 10s = 10800s = 3h
        description="Min polls between scheduled relay checks (~3h at default poll interval)",
    )

    # Discovery pool — generic agents endpoint serving authors the operator
    # has been liking. Currently lives on hub.waow.tech as part of the
    # prefect-server side; consumers (phi here) read it as opaque JSON.
    discovery_pool_url: str = Field(
        default="https://hub.waow.tech/api/agents/discovery-pool",
        description="URL of the discovery-pool JSON endpoint (operator-likes derived)",
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
