from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class WordFeedback(BaseModel):
    word: str
    score: float = Field(ge=0, le=100)
    status: Literal["excellent", "good", "watch", "needs-practice"]
    issue: str
    suggestion: str
    start_ms: int = Field(ge=0, default=0)
    end_ms: int = Field(ge=0, default=0)
    error_type: str = "None"
    confidence: Literal["high", "medium", "low"] = "medium"
    phoneme_hint: str | None = None
    practice_priority: Literal["high", "medium", "low"] = "medium"


class CoachOverview(BaseModel):
    headline: str
    level_label: str
    why: str
    cefr_estimate: str
    confidence_label: str
    improvement_potential: str
    celebration: str


class CoachSummary(BaseModel):
    summary: str
    strengths: list[str]
    weaknesses: list[str]
    speaking_habits: list[str]
    repeated_issue: str
    advice: str


class PriorityIssue(BaseModel):
    word: str
    score: float = Field(ge=0, le=100)
    why: str
    likely_issue: str
    practice_tip: str
    drill: str
    difficulty: Literal["easy", "medium", "hard"]
    priority: Literal["high", "medium", "low"]
    confidence: Literal["high", "medium", "low"]
    start_ms: int = Field(ge=0, default=0)
    end_ms: int = Field(ge=0, default=0)


class PracticeWord(BaseModel):
    word: str
    reason: str
    drill: str
    syllable_hint: str
    repetitions: int = Field(ge=1, le=10)
    estimated_gain: int = Field(ge=0, le=10)


class PracticeSentence(BaseModel):
    sentence: str
    focus_words: list[str]


class PracticePlan(BaseModel):
    today_focus: str
    estimated_score_if_fixed: int = Field(ge=0, le=100)
    estimated_gain: int = Field(ge=0, le=15)
    words: list[PracticeWord]
    sentences: list[PracticeSentence]


class MetricInsight(BaseModel):
    key: Literal["overall", "accuracy", "prosody", "fluency", "completeness"]
    label: str
    score: float = Field(ge=0, le=100)
    band: str
    explanation: str


class CoachInsight(BaseModel):
    title: str
    value: str
    description: str


class AssessmentResponse(BaseModel):
    overall_score: float = Field(ge=0, le=100)
    accuracy_score: float = Field(ge=0, le=100)
    fluency_score: float = Field(ge=0, le=100)
    prosody_score: float = Field(ge=0, le=100)
    completeness_score: float = Field(ge=0, le=100)
    duration_seconds: float = Field(ge=0)
    transcript: str
    summary: str
    coaching: str
    word_feedback: list[WordFeedback]
    top_issues: list[PriorityIssue]
    overview: CoachOverview
    coach_summary: CoachSummary
    practice_plan: PracticePlan
    metrics: list[MetricInsight]
    insights: list[CoachInsight]
    provider_mode: Literal["mock", "azure"] = "mock"


class HistoryItem(AssessmentResponse):
    id: int
    source_type: Literal["upload", "recording"]
    reference_text: str
    created_at: datetime


class DeleteResponse(BaseModel):
    deleted: int
