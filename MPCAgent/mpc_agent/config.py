"""Runtime settings for the MPC agent."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration loaded from environment variables or a local .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    deepseek_api_key: str | None = Field(default=None, alias="DEEPSEEK_API_KEY")
    deepseek_model: str = Field(default="deepseek-v4-flash", alias="DEEPSEEK_MODEL")
    deepseek_api_base: str = Field(
        default="https://api.deepseek.com",
        alias="DEEPSEEK_API_BASE",
    )

    temperature: float = Field(default=0.0, alias="MPC_AGENT_TEMPERATURE")
    max_tokens: int | None = Field(default=4096, alias="MPC_AGENT_MAX_TOKENS")
    request_timeout: float | None = Field(default=60.0, alias="MPC_AGENT_TIMEOUT")
    max_retries: int = Field(default=2, alias="MPC_AGENT_MAX_RETRIES")
    json_mode: bool = Field(default=True, alias="MPC_AGENT_JSON_MODE")

    max_turns: int = Field(default=12, alias="MPC_AGENT_MAX_TURNS")
    max_summary_chars: int = Field(default=3000, alias="MPC_AGENT_MAX_SUMMARY_CHARS")

    mp_spdz_home: str | None = Field(default=None, alias="MPC_AGENT_MP_SPDZ_HOME")


def get_settings() -> Settings:
    return Settings()
