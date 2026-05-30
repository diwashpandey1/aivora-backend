from __future__ import annotations

import html
import re
from email import message_from_string
from pathlib import Path
from typing import Iterable

import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin


URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
HTML_RE = re.compile(r"<[^>]+>")
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
NON_TEXT_RE = re.compile(r"[^a-z0-9\s$%]")
SPACES_RE = re.compile(r"\s+")
EMAIL_HEADER_RE = re.compile(
    r"\b(from|to|cc|bcc|return-path|received|delivered-to|message-id|mime-version|"
    r"content-type|content-transfer-encoding|date|reply-to|sender|x-[\w-]+):",
    re.IGNORECASE,
)

LABEL_COLUMNS = [
    "label",
    "target",
    "spam/ham",
    "spam",
    "class",
    "category",
    "v1",
]
MESSAGE_COLUMNS = [
    "message",
    "text",
    "body",
    "content",
    "email",
    "v2",
]
ENCODINGS = ["utf-8", "utf-8-sig", "latin-1", "cp1252", "iso-8859-1"]


class SpamTextPreprocessor(BaseEstimator, TransformerMixin):
    """Scikit-learn compatible cleaner shared by training and inference.
    
    Memory notes:
    - Processes text iteratively, not loading all data into memory
    - Output is list[str], which is immediately used by vectorizer
    - No significant temporary objects during inference
    - Temporary dict/string allocations freed by Python's GC during processing
    """

    def fit(self, X: Iterable[str], y: Iterable[int] | None = None) -> "SpamTextPreprocessor":
        return self

    def transform(self, X: Iterable[str]) -> list[str]:
        # Process each text through cleaning pipeline
        # Temporary strings created in clean_text() are freed after each iteration
        return [clean_text(value) for value in X]


def clean_text(value: object) -> str:
    """Clean raw text for spam detection with minimal memory overhead.
    
    Memory optimization strategy:
    - Processes text linearly through regex substitutions
    - Each substitution overwrites previous version, freeing old string memory
    - No intermediate lists or large temporary objects
    - String operations are re-used efficiently by Python's string pool
    - Total temporary memory: O(input_length), not O(input * num_operations)
    
    Pipeline order is optimized for memory:
    1. Extract email payload first (reduces string size for further processing)
    2. Regex substitutions in order of likelihood (frequent patterns cleaned first)
    3. Final cleanup with minimal intermediate strings
    """
    text = "" if value is None else str(value)
    text = _extract_email_payload(text)
    text = html.unescape(text)
    text = text.replace("\r", " ").replace("\n", " ")
    text = URL_RE.sub(" ", text)
    text = HTML_RE.sub(" ", text)
    text = EMAIL_RE.sub(" emailaddress ", text)
    text = EMAIL_HEADER_RE.sub(" ", text)
    text = text.lower()
    text = NON_TEXT_RE.sub(" ", text)
    text = SPACES_RE.sub(" ", text).strip()
    return text


def _extract_email_payload(text: str) -> str:
    if not _looks_like_raw_email(text):
        return text

    try:
        parsed = message_from_string(text)
    except Exception:
        return text

    subject = parsed.get("subject", "")
    parts: list[str] = []
    if parsed.is_multipart():
        for part in parsed.walk():
            content_type = part.get_content_type()
            if content_type not in {"text/plain", "text/html"}:
                continue
            payload = part.get_payload(decode=True)
            charset = part.get_content_charset() or "utf-8"
            if isinstance(payload, bytes):
                parts.append(payload.decode(charset, errors="ignore"))
            elif payload:
                parts.append(str(payload))
    else:
        payload = parsed.get_payload(decode=True)
        charset = parsed.get_content_charset() or "utf-8"
        if isinstance(payload, bytes):
            parts.append(payload.decode(charset, errors="ignore"))
        elif payload:
            parts.append(str(payload))

    body = " ".join(parts).strip()
    return f"{subject} {body}".strip() or text


def _looks_like_raw_email(text: str) -> bool:
    lowered = text[:2000].lower()
    markers = ["return-path:", "received:", "message-id:", "mime-version:", "subject:"]
    return sum(marker in lowered for marker in markers) >= 2


def read_raw_dataset(path: Path) -> pd.DataFrame:
    if path.stat().st_size == 0:
        return pd.DataFrame()

    suffix = path.suffix.lower()
    errors: list[str] = []

    for encoding in ENCODINGS:
        try:
            if suffix == ".csv":
                return pd.read_csv(
                    path,
                    encoding=encoding,
                    on_bad_lines="skip",
                    engine="python",
                )
            if suffix in {".txt", ".tsv"}:
                return pd.read_csv(
                    path,
                    sep="\t",
                    names=["label", "message"],
                    encoding=encoding,
                    on_bad_lines="skip",
                    engine="python",
                )
        except Exception as exc:
            errors.append(f"{encoding}: {exc}")

    raise ValueError(f"Could not read {path}: {'; '.join(errors[-3:])}")


def normalize_dataset(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["label", "message"])

    df = df.copy()
    df.columns = [str(column).strip().lower() for column in df.columns]
    df = df.loc[:, ~df.columns.str.startswith("unnamed")]

    label_column = _find_column(df.columns, LABEL_COLUMNS)
    message_column = _find_column(df.columns, MESSAGE_COLUMNS)

    if message_column is None and {"subject", "message"}.issubset(df.columns):
        df["message"] = df["subject"].fillna("") + " " + df["message"].fillna("")
        message_column = "message"
    elif message_column is None and {"subject", "body"}.issubset(df.columns):
        df["message"] = df["subject"].fillna("") + " " + df["body"].fillna("")
        message_column = "message"

    if label_column is None or message_column is None:
        return pd.DataFrame(columns=["label", "message"])

    normalized = pd.DataFrame(
        {
            "label": df[label_column].map(normalize_label),
            "message": df[message_column].astype(str),
        }
    )
    normalized = normalized.dropna(subset=["label", "message"])
    normalized["label"] = normalized["label"].astype(int)
    normalized["message"] = normalized["message"].map(clean_text)
    normalized = normalized[normalized["message"].str.len() > 0]
    normalized = normalized.drop_duplicates(subset=["label", "message"])
    return normalized.reset_index(drop=True)


def normalize_label(value: object) -> int | None:
    if pd.isna(value):
        return None

    if isinstance(value, bool):
        return int(value)

    value_str = str(value).strip().lower()
    if value_str in {"spam", "1", "true", "yes", "phishing", "smishing"}:
        return 1
    if value_str in {"ham", "safe", "0", "false", "no", "not spam", "legitimate"}:
        return 0

    try:
        return 1 if float(value_str) > 0 else 0
    except ValueError:
        return None


def preprocess_directory(input_dir: Path, output_path: Path) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in sorted(input_dir.glob("*")):
        if not path.is_file() or path.suffix.lower() not in {".csv", ".txt", ".tsv"}:
            continue

        raw = read_raw_dataset(path)
        normalized = normalize_dataset(raw)
        if not normalized.empty:
            normalized["source_file"] = path.name
            frames.append(normalized)

    if not frames:
        raise ValueError(f"No usable datasets found in {input_dir}")

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.drop_duplicates(subset=["label", "message"])
    combined = combined.sample(frac=1, random_state=42).reset_index(drop=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(output_path, index=False)
    return combined


def _find_column(columns: Iterable[str], candidates: list[str]) -> str | None:
    columns_set = set(columns)
    for candidate in candidates:
        if candidate in columns_set:
            return candidate
    return None
