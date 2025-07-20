from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    
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
    
    # Server configuration
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Polling configuration
    notification_poll_interval: int = 10  # seconds (faster for testing)
    
    # Debug mode
    debug: bool = False


settings = Settings()  # type: ignore[call-arg]