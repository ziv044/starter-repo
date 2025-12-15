"""Configuration settings for pm6."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from .modes import Mode


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Attributes:
        anthropic_api_key: API key for Anthropic Claude API.
        mode: Operating mode (LIVE, REPLAY, HYBRID).
        log_dir: Directory for JSONL log files.
        strict_replay: If True, raise on missing replay data.
        default_model: Default Claude model to use.
    """

    model_config = SettingsConfigDict(
        env_prefix="PM6_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anthropic_api_key: str = ""
    mode: Mode = Mode.LIVE
    log_dir: Path = Path("./logs")
    strict_replay: bool = True
    default_model: str = "claude-sonnet-4-20250514"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        # Ensure log directory exists
        self.log_dir.mkdir(parents=True, exist_ok=True)


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the global settings instance.

    Returns:
        The Settings instance, creating it if necessary.
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset global settings (useful for testing)."""
    global _settings
    _settings = None
