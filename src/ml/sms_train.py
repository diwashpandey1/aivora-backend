from __future__ import annotations

from src.config import settings
from src.ml.preprocessing import preprocess_directory
from src.ml.train import train_domain


def main() -> None:
    df = preprocess_directory(
        settings.sms_dataset_dir,
        settings.processed_dataset_dir / "sms_processed.csv",
    )
    results = train_domain("sms", df, settings.sms_model_path)
    print(results)


if __name__ == "__main__":
    main()
