from __future__ import annotations

import gc
import re
from pathlib import Path
from typing import Any

import joblib


EMAIL_ADDRESS_RE = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
HEADER_RE = re.compile(r"^(from|to|subject|date|received|return-path):", re.IGNORECASE)


class TypeDetector:
    """Detects whether input is SMS or email for appropriate model selection.
    
    Uses a heuristic first pass (cheap, no ML) then falls back to ML if uncertain.
    Optimized for memory: cleans up temporary feature vectors and predictions.
    """
    
    def __init__(self, model_path: Path) -> None:
        self.model_path = model_path
        self.bundle: dict[str, Any] | None = None

    def load(self) -> None:
        """Load type detector model once during startup (not per-request)."""
        if self.bundle is None and self.model_path.exists():
            self.bundle = joblib.load(self.model_path)

    def detect(self, text: str) -> str:
        """Detect message type with memory-efficient cleanup.
        
        Strategy:
        1. Fast heuristic detection (regex patterns)
        2. ML fallback only if heuristic is uncertain
        3. Clean up temporary ML artifacts immediately after prediction
        """
        heuristic_type, score = self._heuristic(text)
        # Heuristic confidence threshold: 3 points = high confidence, skip ML
        if score >= 3:
            return heuristic_type

        # ML-based detection needed - load model if available
        self.load()
        if self.bundle:
            preprocessor = self.bundle["preprocessor"]
            vectorizer = self.bundle["vectorizer"]
            model = self.bundle["model"]
            
            # Transform text to features (creates temporary numpy/sparse arrays)
            cleaned = preprocessor.transform([text])
            features = vectorizer.transform(cleaned)
            
            # Make prediction
            detected_type = str(model.predict(features)[0])
            
            # CLEANUP: Explicitly delete temporary objects to free memory
            # These can be significant for large vectorizers:
            # - cleaned: list of processed strings
            # - features: sparse matrix (potentially large)
            del cleaned
            del features
            
            # Force garbage collection for ML inference artifacts
            # Prevents accumulation of temporary ML objects between requests
            gc.collect()
            
            return detected_type

        return heuristic_type

    def _heuristic(self, text: str) -> tuple[str, int]:
        """Fast email vs SMS classification using pattern matching.
        
        Email indicators:
        - Email addresses
        - Email headers (From:, Subject:, etc)
        - Multi-line formatting
        - Length
        
        This runs in microseconds with no memory allocation, ideal for
        reducing ML model pressure.
        """
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

