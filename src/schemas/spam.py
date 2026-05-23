from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, Field, field_validator


DetectedType = Literal["sms", "email"]
Prediction = Literal["spam", "safe"]
RiskLevel = Literal["low", "medium", "high"]


class AnalyzeRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=20000,
        validation_alias=AliasChoices("message", "text"),
    )
    client_id: str = Field(
        ...,
        min_length=3,
        max_length=128,
        validation_alias=AliasChoices("client_id", "browser_id"),
    )

    @field_validator("message", "client_id")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class AnalyticsData(BaseModel):
    confidence_chart: list[dict[str, Any]]
    spam_distribution: list[dict[str, Any]]
    keyword_frequency: list[dict[str, Any]]
    prediction_timeline: list[dict[str, Any]]
    pie_chart_values: list[dict[str, Any]]


class AnalyzeResponse(BaseModel):
    detected_type: DetectedType
    prediction: Prediction
    confidence: float
    spam_probability: float
    safe_probability: float
    keywords_detected: list[str]
    risk_level: RiskLevel
    chart_data: dict[str, float]
    analytics: AnalyticsData


class HistoryItem(BaseModel):
    id: str
    client_id: str
    message: str
    detected_type: DetectedType
    prediction: Prediction
    confidence: float
    spam_probability: float
    safe_probability: float = 0.0
    keywords_detected: list[str] = []
    risk_level: RiskLevel
    timestamp: datetime


class HistoryResponse(BaseModel):
    client_id: str
    total: int
    items: list[HistoryItem]


class DeleteHistoryResponse(BaseModel):
    client_id: str
    deleted_count: int


class StatsResponse(BaseModel):
    total_scans: int
    spam_percentage: float
    safe_percentage: float
    type_counts: dict[str, int]
    prediction_counts: dict[str, int]
    keyword_frequency: list[dict[str, Any]]
    prediction_timeline: list[dict[str, Any]]
    pie_chart_values: list[dict[str, Any]]


class HealthResponse(BaseModel):
    status: str
    app: str
    environment: str
    database: str
    models: dict[str, bool]
