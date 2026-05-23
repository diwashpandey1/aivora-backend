from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import joblib


EMAIL_ADDRESS_RE = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
HEADER_RE = re.compile(r"^(from|to|subject|date|received|return-path):", re.IGNORECASE)


class TypeDetector:
    def __init__(self, model_path: Path) -> None:
        self.model_path = model_path
        self.bundle: dict[str, Any] | None = None

    def load(self) -> None:
        if self.bundle is None and self.model_path.exists():
            self.bundle = joblib.load(self.model_path)

    def detect(self, text: str) -> str:
        heuristic_type, score = self._heuristic(text)
        if score >= 3:
            return heuristic_type

        self.load()
        if self.bundle:
            preprocessor = self.bundle["preprocessor"]
            vectorizer = self.bundle["vectorizer"]
            model = self.bundle["model"]
            cleaned = preprocessor.transform([text])
            features = vectorizer.transform(cleaned)
            return str(model.predict(features)[0])

        return heuristic_type

    def _heuristic(self, text: str) -> tuple[str, int]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        email_score = 0

        if EMAIL_ADDRESS_RE.search(text):
            email_score += 2
        if any(HEADER_RE.match(line) for line in lines[:8]):
            email_score += 3
        if re.search(r"\bsubject\s*:", text, flags=re.IGNORECASE):
            email_score += 2
        if len(lines) >= 4:
            email_score += 1
        if len(text) > 500:
            email_score += 1
        if re.search(r"\b(dear|regards|sincerely|unsubscribe)\b", text, re.IGNORECASE):
            email_score += 1

        return ("email", email_score) if email_score >= 2 else ("sms", email_score)
