from __future__ import annotations
from pydantic import BaseModel, Field


class NewSessionRequest(BaseModel):
    player_name: str = Field(default="Anonymous", max_length=40)


class NewSessionResponse(BaseModel):
    session_id: str


class RoundResponse(BaseModel):
    app_id: str
    name: str
    category: str
    description: str
    scopes: list[dict]  # [{id, label, tier, desc}]


class GuessRequest(BaseModel):
    session_id: str
    app_id: str
    guess_tier: str  # "Low" | "Medium" | "High"


class GuessResponse(BaseModel):
    is_correct: bool
    points_earned: int
    ground_truth_tier: str
    ground_truth_score: float
    model_tier: str
    model_score: float
    model_agreed_with_truth: bool
    model_probabilities: dict[str, float]
    reasons: list[str]
    tripped_combos: list[str]
    top_model_features: list[dict]
    session: dict


class AssessAppRequest(BaseModel):
    name: str
    category: str
    scopes: list[str]


class AssessRequest(BaseModel):
    apps: list[AssessAppRequest]


class AssessResultItem(BaseModel):
    name: str
    category: str
    scopes: list[str]
    model_tier: str
    model_score: float
    reasons: list[str]
    unrecognized_scopes: list[str]
