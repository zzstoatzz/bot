from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=[".env"], extra="ignore", populate_by_name=True)

    # Use same env var names as main bot config
    atproto_handle: str = Field(default=..., alias="bluesky_handle")
    atproto_password: str = Field(default=..., alias="bluesky_password")
    atproto_pds_url: str = Field(default="https://bsky.social", alias="bluesky_service")

    atproto_notifications_default_limit: int = Field(default=10)
    atproto_timeline_default_limit: int = Field(default=10)
    atproto_search_default_limit: int = Field(default=10)


settings = Settings()
