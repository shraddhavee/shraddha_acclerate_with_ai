from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env", override=False)


class ConfigurationError(ValueError):
    """Raised when runtime configuration is invalid."""


@dataclass(frozen=True)
class Settings:
    root_dir: Path = ROOT_DIR
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    llm_provider: str = os.getenv("LLM_PROVIDER", "groq")
    groq_api_key: str | None = field(default_factory=lambda: os.getenv("GROQ_API_KEY"), repr=False)

    @property
    def data_dir(self) -> Path:
        return self.root_dir / "data"

    def validate(self, require_api_key: bool = False) -> None:
        provider = self.llm_provider.strip().lower()
        model = self.groq_model.strip()
        key = self.groq_api_key.strip() if self.groq_api_key else ""
        errors = []
        if provider != "groq":
            errors.append("LLM_PROVIDER must be 'groq'")
        if not model:
            errors.append("GROQ_MODEL must not be empty")
        if require_api_key and not key:
            errors.append("GROQ_API_KEY is required when Groq is enabled")
        if key and len(key) < 20:
            errors.append("GROQ_API_KEY is too short")
        if errors:
            raise ConfigurationError("; ".join(errors))

    def ensure_directories(self) -> None:
        for name in ("bronze", "silver", "gold", "sttm", "profiles", "reports", "traces"):
            (self.data_dir / name).mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.validate()
settings.ensure_directories()
