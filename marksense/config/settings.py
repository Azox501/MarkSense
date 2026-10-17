"""The sole environment boundary for credentials, paths and offline defaults."""
from functools import lru_cache
import os
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class AppError(Exception):
    """An actionable message suitable for the interface."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore", populate_by_name=True)
    vision_api_key: SecretStr = Field(default=SecretStr(""), validation_alias="GEMINI_VISION_API_KEY")
    grader_api_key: SecretStr = Field(default=SecretStr(""), validation_alias="GEMINI_GRADER_API_KEY")
    model: str = Field(default="gemini-2.5-flash", validation_alias="GEMINI_MODEL")
    data_dir: Path = Field(default=ROOT / "data", validation_alias="DATA_DIR")
    model_dir: Path = Field(default=ROOT / "data/models", validation_alias="MODEL_DIR")
    similarity_threshold: float = Field(default=0.60, ge=0, le=1, validation_alias="SIMILARITY_THRESHOLD")
    rerank_threshold: float = Field(default=0.3, ge=0, le=1, validation_alias="RERANK_THRESHOLD")

    @model_validator(mode="after")
    def absolute_paths(self) -> "Settings":
        for field in ("data_dir", "model_dir"):
            path = getattr(self, field)
            setattr(self, field, (ROOT / path).resolve() if not path.is_absolute() else path.resolve())
        return self

    def require_credentials(self) -> None:
        """Reject missing or identical credentials without revealing values."""
        if not self.vision_api_key.get_secret_value() or not self.grader_api_key.get_secret_value():
            raise AppError("Configure both Gemini key fields in the local .env file, then restart MarkSense.")
        if self.vision_api_key == self.grader_api_key:
            raise AppError("Configure two different Gemini keys for vision and grading.")

    @property
    def database_path(self) -> Path:
        """Return the SQLite database path."""
        return self.data_dir / "db/marksense.sqlite"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings and disable external tracing/telemetry and model downloads."""
    for name, value in {"LANGSMITH_TRACING":"false", "LANGCHAIN_TRACING_V2":"false",
                        "ANONYMIZED_TELEMETRY":"False", "HF_HUB_OFFLINE":"1", "TRANSFORMERS_OFFLINE":"1"}.items():
        os.environ[name] = value
    return Settings()
