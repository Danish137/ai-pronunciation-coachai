import json

from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session

from ..models.attempt import Attempt
from ..schemas.assessment import (
    AssessmentResponse,
    CoachInsight,
    CoachOverview,
    CoachSummary,
    HistoryItem,
    MetricInsight,
    PracticePlan,
    PracticeSentence,
    PracticeWord,
    PriorityIssue,
    WordFeedback,
)


class AttemptRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        assessment: AssessmentResponse,
        session_id: str,
        source_type: str,
        reference_text: str,
    ) -> HistoryItem:
        attempt = Attempt(
            session_id=session_id,
            source_type=source_type,
            reference_text=reference_text,
            transcript=assessment.transcript,
            overall_score=assessment.overall_score,
            accuracy_score=assessment.accuracy_score,
            fluency_score=assessment.fluency_score,
            prosody_score=assessment.prosody_score,
            completeness_score=assessment.completeness_score,
            duration_seconds=assessment.duration_seconds,
            summary=assessment.summary,
            coaching=assessment.coaching,
            provider_mode=assessment.provider_mode,
            word_feedback_json=json.dumps([item.model_dump() for item in assessment.word_feedback]),
            result_payload_json=assessment.model_dump_json(),
        )
        self.db.add(attempt)
        self.db.commit()
        self.db.refresh(attempt)
        return HistoryItem(**assessment.model_dump(), id=attempt.id, source_type=source_type, reference_text=reference_text, created_at=attempt.created_at)

    def list_for_session(self, session_id: str) -> list[HistoryItem]:
        stmt = select(Attempt).where(Attempt.session_id == session_id).order_by(desc(Attempt.created_at))
        return [self._to_history_item(row) for row in self.db.scalars(stmt).all()]

    def get_for_session(self, session_id: str, attempt_id: int) -> HistoryItem | None:
        stmt = select(Attempt).where(Attempt.session_id == session_id, Attempt.id == attempt_id)
        attempt = self.db.scalars(stmt).first()
        return self._to_history_item(attempt) if attempt else None

    def delete_for_session(self, session_id: str, attempt_id: int) -> bool:
        stmt = delete(Attempt).where(Attempt.session_id == session_id, Attempt.id == attempt_id)
        result = self.db.execute(stmt)
        self.db.commit()
        return result.rowcount > 0

    def delete_history(self, session_id: str) -> int:
        stmt = delete(Attempt).where(Attempt.session_id == session_id)
        result = self.db.execute(stmt)
        self.db.commit()
        return result.rowcount or 0

    def _to_history_item(self, attempt: Attempt) -> HistoryItem:
        if attempt.result_payload_json:
            payload = json.loads(attempt.result_payload_json)
            return HistoryItem(
                **payload,
                id=attempt.id,
                source_type=attempt.source_type,
                reference_text=attempt.reference_text,
                created_at=attempt.created_at,
            )

        word_feedback = [WordFeedback(**item) for item in json.loads(attempt.word_feedback_json)]
        top_words = [word for word in word_feedback if word.status in {"watch", "needs-practice"}][:5]
        average_target = min(100, round(attempt.overall_score + max(2, len(top_words)), 0))

        return HistoryItem(
            id=attempt.id,
            source_type=attempt.source_type,
            reference_text=attempt.reference_text,
            transcript=attempt.transcript,
            overall_score=attempt.overall_score,
            accuracy_score=attempt.accuracy_score,
            fluency_score=attempt.fluency_score,
            prosody_score=attempt.prosody_score,
            completeness_score=attempt.completeness_score,
            duration_seconds=attempt.duration_seconds,
            summary=attempt.summary,
            coaching=attempt.coaching,
            provider_mode=attempt.provider_mode or "mock",
            word_feedback=word_feedback,
            top_issues=[
                PriorityIssue(
                    word=word.word,
                    score=word.score,
                    why=word.issue,
                    likely_issue=word.issue,
                    practice_tip=word.suggestion,
                    drill=f"Repeat {word.word} five times with steadier stress.",
                    difficulty="medium",
                    priority=word.practice_priority,
                    confidence=word.confidence,
                    start_ms=word.start_ms,
                    end_ms=word.end_ms,
                )
                for word in top_words
            ],
            overview=CoachOverview(
                headline=f"{round(attempt.overall_score)}/100",
                level_label="Pronunciation snapshot",
                why=attempt.summary,
                cefr_estimate="B2",
                confidence_label="Medium confidence",
                improvement_potential="Moderate improvement available",
                celebration="You already have a usable speaking base. Focus on the flagged words to climb faster.",
            ),
            coach_summary=CoachSummary(
                summary=attempt.coaching or attempt.summary,
                strengths=["Clearer words stayed stable across the sample."],
                weaknesses=["A few low-scoring words caused most deductions."],
                speaking_habits=["Steady pacing on familiar words."],
                repeated_issue="Word stress and articulation need the most attention.",
                advice="Practice the highlighted words first instead of repeating the whole recording.",
            ),
            practice_plan=PracticePlan(
                today_focus="Fix the lowest-scoring words first.",
                estimated_score_if_fixed=average_target,
                estimated_gain=max(2, average_target - round(attempt.overall_score)),
                words=[
                    PracticeWord(
                        word=word.word,
                        reason=word.issue,
                        drill=word.suggestion,
                        syllable_hint=word.word,
                        repetitions=5,
                        estimated_gain=1,
                    )
                    for word in top_words
                ],
                sentences=[
                    PracticeSentence(sentence=f"I can say {word.word} clearly in a full sentence.", focus_words=[word.word])
                    for word in top_words[:3]
                ],
            ),
            metrics=[
                MetricInsight(key="overall", label="Overall", score=attempt.overall_score, band="Good", explanation=attempt.summary),
                MetricInsight(key="accuracy", label="Accuracy", score=attempt.accuracy_score, band="Good", explanation="Most words were recognizable, but a few lost clarity."),
                MetricInsight(key="prosody", label="Prosody", score=attempt.prosody_score, band="Developing", explanation="Sentence rhythm and stress could sound more natural."),
                MetricInsight(key="fluency", label="Fluency", score=attempt.fluency_score, band="Good", explanation="Flow was mostly steady with a few interruptions."),
                MetricInsight(key="completeness", label="Completeness", score=attempt.completeness_score, band="Strong", explanation="Most of the spoken content was captured."),
            ],
            insights=[
                CoachInsight(title="Consistency", value="Stable", description="Your clearer words are already sounding repeatable."),
                CoachInsight(title="Focus", value=str(len(top_words)), description="Only a handful of words are holding back the overall score."),
            ],
            created_at=attempt.created_at,
        )
