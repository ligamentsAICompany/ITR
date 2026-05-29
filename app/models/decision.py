"""Pydantic models for deterministic ITR decision outputs."""

from typing import Any
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ITRDecisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_itr: str
    reason_codes: list[str]
    missing_fields: list[str]
    confidence: Literal["high", "medium", "low"]


class MissingFieldsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    missing_fields: list[str]


class ExplanationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_itr: str
    explanation: str
    reason_codes: list[str]
    missing_fields: list[str]
    confidence: Literal["high", "medium", "low"]


class ClarificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    missing_fields: list[str]
    context: dict[str, Any] = Field(default_factory=dict)


class ClarificationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
