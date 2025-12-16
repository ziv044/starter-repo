"""pm6 configuration settings using pydantic-settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """pm6 configuration settings.

    Settings are loaded from environment variables with PM6_ prefix,
    or from a .env file in the current directory.

    Attributes:
        anthropicApiKey: Anthropic API key for Claude access.
        dbPath: Path to the database storage directory.
        defaultModel: Default model for agent responses.
        compactionModel: Model used for context compaction (cheaper).
        costLimitPerSession: Maximum cost allowed per session.
        costLimitPerInteraction: Maximum cost allowed per interaction.
        logLevel: Logging level.
    """

    model_config = SettingsConfigDict(
        env_prefix="PM6_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API Configuration
    anthropicApiKey: str = Field(
        default="",
        alias="ANTHROPIC_API_KEY",
        description="Anthropic API key",
    )

    # Storage Configuration
    dbPath: Path = Field(
        default=Path("./db"),
        description="Path to database storage directory",
    )

    # Model Configuration
    defaultModel: str = Field(
        default="claude-sonnet-4-20250514",
        description="Default model for agent responses",
    )
    compactionModel: str = Field(
        default="claude-haiku-3-20240307",
        description="Model for context compaction",
    )

    # Cost Limits
    costLimitPerSession: float = Field(
        default=10.0,
        description="Maximum cost per session in USD",
    )
    costLimitPerInteraction: float = Field(
        default=1.0,
        description="Maximum cost per interaction in USD",
    )

    # Logging
    logLevel: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Logging level",
    )

    def ensureDbPath(self) -> Path:
        """Ensure the database path exists and return it.

        Returns:
            Path to the database directory.
        """
        self.dbPath.mkdir(parents=True, exist_ok=True)
        return self.dbPath


@lru_cache
def getSettings() -> Settings:
    """Get cached settings instance.

    Returns:
        Singleton Settings instance.
    """
    return Settings()
