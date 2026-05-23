from __future__ import annotations

import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from src.config import settings
from src.ml.type_detection import TypeDetector
from src.utils.logger import get_logger


SPAM_KEYWORDS = {
    "free",
    "winner",
    "win",
    "claim",
    "urgent",
    "cash",
    "prize",
    "click",
    "limited",
    "offer",
    "guaranteed",
    "congratulations",
    "verify",
    "account",
    "password",
    "selected",
    "unsubscribe",
    "credit",
    "loan",
    "deal",
}


logger = get_logger(__name__)


class ModelNotReadyError(RuntimeError):
    pass


class PredictionService:
    def __init__(self) -> None:
        self._bundles: dict[str, dict[str, Any]] = {}
        self._type_detector = TypeDetector(settings.type_detector_path)

    def models_status(self) -> dict[str, bool]:
        return {
            "sms": settings.sms_model_path.exists(),
            "email": settings.email_model_path.exists(),
            "type_detector": settings.type_detector_path.exists(),
        }

    def warmup(self) -> None:
        """Load persisted models once so inference never retrains per request."""
        self._type_detector.load()
        for detected_type in ("sms", "email"):
            try:
                self._load_bundle(detected_type)
            except ModelNotReadyError as exc:
                logger.warning("Model warmup skipped for %s: %s", detected_type, exc)

    def analyze(self, text: str) -> dict[str, Any]:
        detected_type = self._type_detector.detect(text)
        bundle = self._load_bundle(detected_type)

        preprocessor = bundle["preprocessor"]
        vectorizer = bundle["vectorizer"]
        model = bundle["model"]

        cleaned = preprocessor.transform([text])
        features = vectorizer.transform(cleaned)

        spam_probability = self._spam_probability(model, features)
        safe_probability = 1 - spam_probability
        prediction = "spam" if spam_probability >= 0.5 else "safe"
        confidence = round(max(spam_probability, safe_probability) * 100, 2)
        keywords = self._extract_keywords(cleaned[0], vectorizer, features, model)
        risk_level = self._risk_level(spam_probability)

        return {
            "detected_type": detected_type,
            "prediction": prediction,
            "confidence": confidence,
            "spam_probability": round(spam_probability, 4),
            "safe_probability": round(safe_probability, 4),
            "keywords_detected": keywords,
            "risk_level": risk_level,
            "chart_data": {
                "spam_score": round(spam_probability * 100),
                "safe_score": round(safe_probability * 100),
            },
            "analytics": self._analytics_payload(
                prediction=prediction,
                confidence=confidence,
                spam_probability=spam_probability,
                detected_type=detected_type,
                keywords=keywords,
            ),
        }

    def _load_bundle(self, detected_type: str) -> dict[str, Any]:
        if detected_type in self._bundles:
            return self._bundles[detected_type]

        path = settings.email_model_path if detected_type == "email" else settings.sms_model_path
        if not Path(path).exists():
            raise ModelNotReadyError(
                f"{detected_type} model is missing. Run: python -m src.ml.train --domain all"
            )

        bundle = joblib.load(path)
        self._bundles[detected_type] = bundle
        return bundle

    def _spam_probability(self, model: Any, features: Any) -> float:
        if hasattr(model, "predict_proba"):
            probabilities = model.predict_proba(features)[0]
            classes = list(model.classes_)
            spam_index = classes.index(1) if 1 in classes else classes.index("spam")
            return float(probabilities[spam_index])

        if hasattr(model, "decision_function"):
            score = float(model.decision_function(features)[0])
            return 1.0 / (1.0 + math.exp(-score))

        prediction = model.predict(features)[0]
        return 1.0 if prediction in {1, "spam"} else 0.0

    def _extract_keywords(
        self,
        cleaned_text: str,
        vectorizer: Any,
        features: Any,
        model: Any,
    ) -> list[str]:
        tokens = [token for token in cleaned_text.split() if len(token) > 2]
        suspicious = [token for token in tokens if token in SPAM_KEYWORDS]

        feature_names = np.array(vectorizer.get_feature_names_out())
        non_zero = features.nonzero()[1]
        if len(non_zero) == 0:
            return list(dict.fromkeys(suspicious))[:8]

        weights = np.asarray(features[:, non_zero].todense()).ravel()
        ranked = feature_names[non_zero][np.argsort(weights)[::-1]]

        spam_terms = self._spam_weighted_terms(model, vectorizer, ranked)
        candidates = suspicious + spam_terms + [term for term in ranked if " " not in term]
        deduped = list(dict.fromkeys(str(term) for term in candidates if len(str(term)) > 2))
        return deduped[:8]

    def _spam_weighted_terms(
        self,
        model: Any,
        vectorizer: Any,
        ranked_terms: np.ndarray,
    ) -> list[str]:
        feature_names = np.array(vectorizer.get_feature_names_out())
        spam_weights: np.ndarray | None = None

        if hasattr(model, "coef_"):
            spam_weights = np.asarray(model.coef_).ravel()
        elif hasattr(model, "feature_log_prob_") and len(model.feature_log_prob_) >= 2:
            spam_weights = model.feature_log_prob_[1] - model.feature_log_prob_[0]

        if spam_weights is None:
            return [term for term in ranked_terms[:8] if " " not in term]

        index = {term: i for i, term in enumerate(feature_names)}
        weighted_terms = []
        for term in ranked_terms:
            term_str = str(term)
            if " " in term_str or term_str not in index:
                continue
            if spam_weights[index[term_str]] > 0:
                weighted_terms.append(term_str)
        return weighted_terms[:8]

    def _risk_level(self, spam_probability: float) -> str:
        if spam_probability >= 0.75:
            return "high"
        if spam_probability >= 0.45:
            return "medium"
        return "low"

    def _analytics_payload(
        self,
        prediction: str,
        confidence: float,
        spam_probability: float,
        detected_type: str,
        keywords: list[str],
    ) -> dict[str, Any]:
        safe_probability = 1 - spam_probability
        now = datetime.now(timezone.utc)
        keyword_counts = Counter(keywords)

        return {
            "confidence_chart": [
                {"label": "confidence", "value": confidence},
                {"label": "uncertainty", "value": round(100 - confidence, 2)},
            ],
            "spam_distribution": [
                {"label": "spam", "value": round(spam_probability * 100, 2)},
                {"label": "safe", "value": round(safe_probability * 100, 2)},
            ],
            "keyword_frequency": [
                {"keyword": keyword, "count": count}
                for keyword, count in keyword_counts.items()
            ],
            "prediction_timeline": [
                {
                    "timestamp": now.isoformat(),
                    "prediction": prediction,
                    "detected_type": detected_type,
                    "confidence": confidence,
                }
            ],
            "pie_chart_values": [
                {"label": "spam", "value": round(spam_probability, 4)},
                {"label": "safe", "value": round(safe_probability, 4)},
            ],
        }


prediction_service = PredictionService()
