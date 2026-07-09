from datetime import datetime
from typing import Any
from typing import Literal

from pydantic import BaseModel, Field


class PhonemeFeedback(BaseModel):
    phoneme: str
    ipa: str | None = None
    accuracy_score: float = Field(ge=0, le=100)
    offset_ms: int = Field(ge=0, default=0)
    duration_ms: int = Field(ge=0, default=0)
    error_type: str = "None"


class SyllableFeedback(BaseModel):
    syllable: str
    grapheme: str | None = None
    accuracy_score: float = Field(ge=0, le=100)
    offset_ms: int = Field(ge=0, default=0)
    duration_ms: int = Field(ge=0, default=0)
    stress_level: str | None = None
    phonemes: list[PhonemeFeedback] = []


class WordFeedback(BaseModel):
    word: str
    score: float = Field(ge=0, le=100)
    status: Literal["excellent", "good", "watch", "needs-practice"]
    issue: str
    suggestion: str
    start_ms: int = Field(ge=0, default=0)
    end_ms: int = Field(ge=0, default=0)
    duration_ms: int = Field(ge=0, default=0)
    error_type: str = "None"
    confidence: Literal["high", "medium", "low"] = "medium"
    phoneme_hint: str | None = None
    practice_priority: Literal["high", "medium", "low"] = "medium"
    ipa: str | None = None
    syllables: list[str] = []
    stress_syllable: int | None = None
    native_pronunciation: str | None = None
    slow_pronunciation: str | None = None
    affected_phonemes: list[str] = []
    affected_syllable: str | None = None
    pronunciation_explanation: str | None = None
    detected_issue_categories: list[str] = []
    phoneme_details: list[PhonemeFeedback] = []
    syllable_details: list[SyllableFeedback] = []
    azure_confidence_score: float | None = Field(default=None, ge=0, le=100)
    evidence_summary: str | None = None
    prosody_score: float | None = Field(default=None, ge=0, le=100)
    syllable_accuracy_score: float | None = Field(default=None, ge=0, le=100)
    completeness_score: float | None = Field(default=None, ge=0, le=100)
    expected_stress_pattern: str | None = None
    detected_stress_pattern: str | None = None
    raw_breakdown: dict[str, Any] = {}


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
    ipa: str | None = None
    syllables: list[str] = []
    stress_syllable: int | None = None
    native_pronunciation: str | None = None
    slow_pronunciation: str | None = None


class PracticeWord(BaseModel):
    word: str
    reason: str
    drill: str
    syllable_hint: str
    ipa: str | None = None
    stress_syllable: int | None = None
    native_pronunciation: str | None = None
    slow_pronunciation: str | None = None
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


class AzureDiagnosticsSummary(BaseModel):
    reference_text_used: str
    recognized_text: str
    overall_scores: dict[str, float]
    prosody: dict[str, Any]
    flagged_word_count: int = Field(ge=0)
    issue_category_counts: dict[str, int] = {}
    segment_count: int = Field(ge=0)
    word_count: int = Field(ge=0)
    patterns: list[str] = []
    assessment_metadata: dict[str, Any] = {}
    flagged_words: list[dict[str, Any]] = []
    transcript_words: list[dict[str, Any]] = []
    segments: list[dict[str, Any]] = []


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
    raw_azure_json: dict | list | None = None
    azure_diagnostics: AzureDiagnosticsSummary | None = None


class HistoryItem(AssessmentResponse):
    id: int
    source_type: Literal["upload", "recording"]
    reference_text: str
    created_at: datetime


class DeleteResponse(BaseModel):
    deleted: int


class RawAzurePayloadResponse(BaseModel):
    attempt_id: int
    provider_mode: Literal["mock", "azure"]
    raw_azure_json: dict | list | None
