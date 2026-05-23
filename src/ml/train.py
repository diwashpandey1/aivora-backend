from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.svm import LinearSVC

from src.config import settings
from src.ml.preprocessing import SpamTextPreprocessor, preprocess_directory


def train_all() -> dict[str, Any]:
    settings.models_dir.mkdir(parents=True, exist_ok=True)
    settings.processed_dataset_dir.mkdir(parents=True, exist_ok=True)

    sms_df = preprocess_directory(
        settings.sms_dataset_dir,
        settings.processed_dataset_dir / "sms_processed.csv",
    )
    email_df = preprocess_directory(
        settings.email_dataset_dir,
        settings.processed_dataset_dir / "email_processed.csv",
    )

    results = {
        "sms": train_domain("sms", sms_df, settings.sms_model_path),
        "email": train_domain("email", email_df, settings.email_model_path),
        "type_detector": train_type_detector(sms_df, email_df, settings.type_detector_path),
    }

    metrics_path = settings.models_dir / "training_metrics.json"
    metrics_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return results


def train_domain(domain: str, df: pd.DataFrame, output_path: Path) -> dict[str, Any]:
    if settings.max_train_rows:
        df = df.sample(
            n=min(settings.max_train_rows, len(df)),
            random_state=42,
        ).reset_index(drop=True)

    X = df["message"].astype(str)
    y = df["label"].astype(int)

    if y.nunique() < 2:
        raise ValueError(f"{domain} dataset must contain both spam and safe labels.")

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.98,
        sublinear_tf=True,
    )
    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)

    candidates = {
        "MultinomialNB": MultinomialNB(),
        "LogisticRegression": LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
            solver="liblinear",
        ),
        "LinearSVC": CalibratedClassifierCV(
            estimator=LinearSVC(class_weight="balanced"),
            cv=3,
        ),
    }

    scores: dict[str, dict[str, float]] = {}
    fitted_models: dict[str, Any] = {}

    for name, model in candidates.items():
        model.fit(X_train_vec, y_train)
        predictions = model.predict(X_test_vec)
        scores[name] = {
            "precision": round(precision_score(y_test, predictions, zero_division=0), 4),
            "recall": round(recall_score(y_test, predictions, zero_division=0), 4),
            "f1_score": round(f1_score(y_test, predictions, zero_division=0), 4),
            "accuracy": round(accuracy_score(y_test, predictions), 4),
        }
        fitted_models[name] = model

    best_name = max(
        scores,
        key=lambda key: (scores[key]["f1_score"], scores[key]["accuracy"]),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "domain": domain,
            "model_name": best_name,
            "model": fitted_models[best_name],
            "vectorizer": vectorizer,
            "preprocessor": SpamTextPreprocessor(),
            "metrics": scores,
            "label_map": {0: "safe", 1: "spam"},
        },
        output_path,
    )

    return {
        "rows": int(len(df)),
        "best_model": best_name,
        "metrics": scores,
        "model_path": str(output_path),
    }


def train_type_detector(
    sms_df: pd.DataFrame,
    email_df: pd.DataFrame,
    output_path: Path,
) -> dict[str, Any]:
    sms = pd.DataFrame({"message": sms_df["message"], "type": "sms"})
    email = pd.DataFrame({"message": email_df["message"], "type": "email"})
    df = pd.concat([sms, email], ignore_index=True).drop_duplicates("message")

    if settings.max_train_rows:
        df = df.sample(
            n=min(settings.max_train_rows, len(df)),
            random_state=42,
        ).reset_index(drop=True)

    X_train, X_test, y_train, y_test = train_test_split(
        df["message"],
        df["type"],
        test_size=0.2,
        random_state=42,
        stratify=df["type"],
    )

    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2)
    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)

    model = LogisticRegression(max_iter=500, class_weight="balanced", solver="liblinear")
    model.fit(X_train_vec, y_train)
    predictions = model.predict(X_test_vec)
    accuracy = round(accuracy_score(y_test, predictions), 4)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "vectorizer": vectorizer,
            "preprocessor": SpamTextPreprocessor(),
            "accuracy": accuracy,
        },
        output_path,
    )

    return {"rows": int(len(df)), "accuracy": accuracy, "model_path": str(output_path)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Train spam detection models.")
    parser.add_argument("--domain", choices=["all", "sms", "email"], default="all")
    args = parser.parse_args()

    if args.domain == "all":
        results = train_all()
    elif args.domain == "sms":
        df = preprocess_directory(
            settings.sms_dataset_dir,
            settings.processed_dataset_dir / "sms_processed.csv",
        )
        results = {"sms": train_domain("sms", df, settings.sms_model_path)}
    else:
        df = preprocess_directory(
            settings.email_dataset_dir,
            settings.processed_dataset_dir / "email_processed.csv",
        )
        results = {"email": train_domain("email", df, settings.email_model_path)}

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
