from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency is listed for production.
    load_dotenv = None


BASE_DIR = Path(__file__).resolve().parents[1]

if load_dotenv:
    load_dotenv(BASE_DIR / ".env")


def _env(name: str, default: str) -> str:
    return os.getenv(name, default).strip()


def _optional_int(name: str) -> int | None:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return None
    return int(value)


def _csv_env(name: str, default: str) -> list[str]:
    return [item.strip() for item in _env(name, default).split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    app_name: str = _env("APP_NAME", "Spam Detector API")
    environment: str = _env("ENVIRONMENT", "development")
    api_version: str = _env("API_VERSION", "v1")
    log_level: str = _env("LOG_LEVEL", "INFO")
    cors_origins: list[str] = None

    mongodb_uri: str = _env("MONGODB_URI", "mongodb://localhost:27017")
    mongodb_database: str = _env("MONGODB_DATABASE", "spam_detector")
    mongodb_collection: str = _env("MONGODB_COLLECTION", "scans")
    mongodb_server_selection_timeout_ms: int = int(
        _env("MONGODB_SERVER_SELECTION_TIMEOUT_MS", "2500")
    )

    dataset_dir: Path = BASE_DIR / _env("DATASET_DIR", "dataset")
    models_dir: Path = BASE_DIR / _env("MODELS_DIR", "models_saved")
    processed_dataset_dir: Path = BASE_DIR / _env(
        "PROCESSED_DATASET_DIR", "dataset/processed"
    )
    max_train_rows: int | None = _optional_int("MAX_TRAIN_ROWS")

    @property
    def sms_dataset_dir(self) -> Path:
        return self.dataset_dir / "sms_spam"

    @property
    def email_dataset_dir(self) -> Path:
        return self.dataset_dir / "email_spam"

    @property
    def sms_model_path(self) -> Path:
        return self.models_dir / "sms" / "model_bundle.joblib"

    @property
    def email_model_path(self) -> Path:
        return self.models_dir / "email" / "model_bundle.joblib"

    @property
    def type_detector_path(self) -> Path:
        return self.models_dir / "type_detector.joblib"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "cors_origins",
            _csv_env("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"),
        )


settings = Settings()
