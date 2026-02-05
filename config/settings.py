from enum import StrEnum

from pydantic import Field  # noqa: F401 — used by submodules
from pydantic_settings import BaseSettings


class LLMProvider(StrEnum):
    OLLAMA = "ollama"
    CLAUDE = "claude"
    GEMINI = "gemini"
    OPENAI = "openai"


class Settings(BaseSettings):
    # LLM routing
    default_provider: LLMProvider = LLMProvider.OLLAMA
    sensitive_screening_provider: LLMProvider = LLMProvider.OLLAMA  # always local first
    high_quality_provider: LLMProvider = LLMProvider.CLAUDE  # for deep analysis after screening

    # Ollama
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_vision_model: str = "qwen2.5-vl:7b"

    # Cloud providers (optional)
    claude_api_key: str = ""
    claude_model: str = "claude-sonnet-4-5-20250929"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # Gmail
    google_client_id: str = ""
    google_client_secret: str = ""

    # Database
    database_url: str = "sqlite+aiosqlite:///data/automate.db"

    # Processing
    email_batch_size: int = 50  # emails per review batch
    bookmark_fetch_timeout: int = 30  # seconds

    log_level: str = "INFO"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
