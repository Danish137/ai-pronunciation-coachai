import hashlib
import json
import logging
from collections import Counter
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import HTTPException, status

from ..core.config import get_settings
from ..schemas.assessment import (
    AssessmentResponse,
    AzureDiagnosticsSummary,
    CoachInsight,
    CoachOverview,
    CoachSummary,
    MetricInsight,
    PhonemeFeedback,
    PracticePlan,
    PracticeSentence,
    PracticeWord,
    PriorityIssue,
    SyllableFeedback,
    WordFeedback,
)

settings = get_settings()
logger = logging.getLogger("pronounceai.analysis")

ARPABET_TO_IPA = {
    "AA": "a",
    "AE": "ae",
    "AH": "uh",
    "AO": "aw",
    "AW": "ow",
    "AY": "eye",
    "B": "b",
    "CH": "ch",
    "D": "d",
    "DH": "dh",
    "EH": "eh",
    "ER": "er",
    "EY": "ay",
    "F": "f",
    "G": "g",
    "HH": "h",
    "IH": "ih",
    "IY": "ee",
    "JH": "j",
    "K": "k",
    "L": "l",
    "M": "m",
    "N": "n",
    "NG": "ng",
    "OW": "oh",
    "OY": "oy",
    "P": "p",
    "R": "r",
    "S": "s",
    "SH": "sh",
    "T": "t",
    "TH": "th",
    "UH": "oo",
    "UW": "u",
    "V": "v",
    "W": "w",
    "Y": "y",
    "Z": "z",
    "ZH": "zh",
}


@dataclass
class ProviderInputs:
    normalized_audio_path: str
    reference_text: str
    duration_seconds: float


@dataclass
class RawAssessment:
    overall_score: float
    accuracy_score: float
    fluency_score: float
    prosody_score: float
    completeness_score: float
    duration_seconds: float
    transcript: str
    word_feedback: list[WordFeedback]
    provider_mode: str
    raw_azure_json: dict | list | None = None
    azure_diagnostics: AzureDiagnosticsSummary | None = None


class AssessmentService:
    async def analyze(self, inputs: ProviderInputs) -> AssessmentResponse:
        if settings.enable_mock_analysis or not (settings.azure_speech_key and settings.azure_speech_region):
            raw_assessment = await self._mock_assessment(inputs)
        else:
            raw_assessment = await self._azure_assessment(inputs)
        response = await self._compose_response(raw_assessment)
        logger.warning("FINAL_ASSESSMENT_RESPONSE %s", response.model_dump_json())
        return response

    async def _azure_assessment(self, inputs: ProviderInputs) -> RawAssessment:
        try:
            import azure.cognitiveservices.speech as speechsdk  # type: ignore[import-not-found]
        except ImportError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Azure Speech SDK is not installed. Install backend requirements in the project venv.",
            ) from exc

        speech_config = speechsdk.SpeechConfig(subscription=settings.azure_speech_key, region=settings.azure_speech_region)
        speech_config.speech_recognition_language = "en-US"

        effective_reference_text = inputs.reference_text.strip() or await self._transcribe_audio(
            speechsdk=speechsdk,
            speech_config=speech_config,
            audio_path=inputs.normalized_audio_path,
        )
        audio_config = speechsdk.audio.AudioConfig(filename=inputs.normalized_audio_path)
        recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

        assessment_config = speechsdk.PronunciationAssessmentConfig(
            reference_text=effective_reference_text,
            grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
            granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
            enable_miscue=True,
        )
        assessment_config.enable_prosody_assessment()
        assessment_config.apply_to(recognizer)

        transcript_parts: list[str] = []
        word_feedback: list[WordFeedback] = []
        segment_scores: list[dict[str, float]] = []
        raw_segments: list[dict[str, Any]] = []
        done = {"value": False}

        def stop_cb(_: object) -> None:
            done["value"] = True

        def recognized_cb(evt: object) -> None:
            result = evt.result
            if result.reason != speechsdk.ResultReason.RecognizedSpeech:
                return
            if result.text:
                transcript_parts.append(result.text)

            raw_json = json.loads(result.properties.get(speechsdk.PropertyId.SpeechServiceResponse_JsonResult))
            raw_segments.append(raw_json)
            nbest = raw_json.get("NBest", [{}])[0]
            pa = nbest.get("PronunciationAssessment", {})
            segment_scores.append(
                {
                    "accuracy": float(pa.get("AccuracyScore", 0)),
                    "fluency": float(pa.get("FluencyScore", 0)),
                    "prosody": float(pa.get("ProsodyScore", 0)),
                    "completeness": float(pa.get("CompletenessScore", 0)),
                }
            )
            for word_payload in nbest.get("Words", []):
                parsed_word = self._build_word_feedback(word_payload)
                if parsed_word.word:
                    word_feedback.append(parsed_word)

        recognizer.recognized.connect(recognized_cb)
        recognizer.session_stopped.connect(stop_cb)
        recognizer.canceled.connect(stop_cb)
        recognizer.start_continuous_recognition()

        import asyncio

        for _ in range(600):
            if done["value"]:
                break
            await asyncio.sleep(0.1)

        recognizer.stop_continuous_recognition()

        if not transcript_parts or not word_feedback:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Azure Speech could not analyze the audio.")

        aggregate = self._aggregate_scores(segment_scores, word_feedback)
        recognized_text = " ".join(transcript_parts).strip()
        diagnostics = self._build_azure_diagnostics(
            word_feedback=word_feedback,
            reference_text=effective_reference_text,
            recognized_text=recognized_text,
            scores=aggregate,
            raw_segments=raw_segments,
        )
        logger.warning("AZURE_NORMALIZED_EVIDENCE %s", diagnostics.model_dump_json())

        return RawAssessment(
            overall_score=aggregate["overall"],
            accuracy_score=aggregate["accuracy"],
            fluency_score=aggregate["fluency"],
            prosody_score=aggregate["prosody"],
            completeness_score=aggregate["completeness"],
            duration_seconds=inputs.duration_seconds,
            transcript=recognized_text,
            word_feedback=word_feedback[:200],
            provider_mode="azure",
            raw_azure_json={
                "reference_text_used": effective_reference_text,
                "recognized_text": recognized_text,
                "segments": raw_segments,
            },
            azure_diagnostics=diagnostics,
        )

    async def _transcribe_audio(self, speechsdk: object, speech_config: object, audio_path: str) -> str:
        audio_config = speechsdk.audio.AudioConfig(filename=audio_path)
        recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
        transcript_parts: list[str] = []
        done = {"value": False}

        def stop_cb(_: object) -> None:
            done["value"] = True

        def recognized_cb(evt: object) -> None:
            result = evt.result
            if result.reason != speechsdk.ResultReason.RecognizedSpeech:
                return
            if result.text:
                transcript_parts.append(result.text)

        recognizer.recognized.connect(recognized_cb)
        recognizer.session_stopped.connect(stop_cb)
        recognizer.canceled.connect(stop_cb)
        recognizer.start_continuous_recognition()

        import asyncio

        for _ in range(600):
            if done["value"]:
                break
            await asyncio.sleep(0.1)

        recognizer.stop_continuous_recognition()
        transcript = " ".join(transcript_parts).strip()
        if not transcript:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not transcribe the uploaded English speech for assessment.",
            )
        return transcript

    def _build_word_feedback(self, word_payload: dict[str, Any]) -> WordFeedback:
        pronunciation = word_payload.get("PronunciationAssessment", {})
        word = (word_payload.get("Word", "") or "").strip()
        score = float(pronunciation.get("AccuracyScore", 0))
        error_type = pronunciation.get("ErrorType", "None")
        offset_ms = int(word_payload.get("Offset", 0) / 10000)
        duration_ms = int(word_payload.get("Duration", 0) / 10000)
        prosody_score = self._optional_float(pronunciation.get("ProsodyScore"))
        syllable_accuracy = self._optional_float(pronunciation.get("SyllableScore"))
        completeness_score = self._optional_float(pronunciation.get("CompletenessScore"))

        phoneme_details = self._build_phoneme_details(word_payload.get("Phonemes", []))
        syllable_details = self._build_syllable_details(word_payload.get("Syllables", []), phoneme_details)
        affected_phonemes = [item.phoneme for item in sorted(phoneme_details, key=lambda item: item.accuracy_score) if item.accuracy_score < 80][:4]
        weakest_syllable = min(syllable_details, key=lambda item: item.accuracy_score) if syllable_details else None
        affected_syllable = weakest_syllable.syllable if weakest_syllable and weakest_syllable.accuracy_score < 82 else None
        issue_categories = self._issue_categories(error_type, phoneme_details, syllable_details, pronunciation)
        pronunciation_meta = self._word_pronunciation_meta(word)
        evidence_confidence = self._confidence_from_evidence(score, error_type, phoneme_details, syllable_details)
        evidence_summary = self._evidence_summary(error_type, phoneme_details, syllable_details, pronunciation)
        stress_pattern = self._stress_pattern(syllable_details)

        return WordFeedback(
            word=word,
            score=score,
            status=self._status_from_score(score),
            issue="",
            suggestion="",
            start_ms=offset_ms,
            end_ms=offset_ms + duration_ms,
            duration_ms=duration_ms,
            error_type=error_type,
            confidence=evidence_confidence,
            phoneme_hint=", ".join(affected_phonemes[:3]) if affected_phonemes else None,
            practice_priority=self._priority_from_score(score),
            ipa=pronunciation_meta["ipa"],
            syllables=pronunciation_meta["syllables"],
            stress_syllable=pronunciation_meta["stress_syllable"],
            native_pronunciation=pronunciation_meta["native_pronunciation"],
            slow_pronunciation=pronunciation_meta["slow_pronunciation"],
            affected_phonemes=affected_phonemes,
            affected_syllable=affected_syllable,
            pronunciation_explanation=None,
            detected_issue_categories=issue_categories,
            phoneme_details=phoneme_details,
            syllable_details=syllable_details,
            azure_confidence_score=score,
            evidence_summary=evidence_summary,
            prosody_score=prosody_score,
            syllable_accuracy_score=syllable_accuracy,
            completeness_score=completeness_score,
            expected_stress_pattern=pronunciation_meta["expected_stress_pattern"],
            detected_stress_pattern=stress_pattern,
            raw_breakdown={
                "accuracy_score": score,
                "error_type": error_type,
                "offset_ms": offset_ms,
                "duration_ms": duration_ms,
                "prosody_score": prosody_score,
                "syllable_accuracy_score": syllable_accuracy,
                "completeness_score": completeness_score,
                "phoneme_count": len(phoneme_details),
                "syllable_count": len(syllable_details),
            },
        )

    def _build_phoneme_details(self, phoneme_payloads: list[dict[str, Any]]) -> list[PhonemeFeedback]:
        items: list[PhonemeFeedback] = []
        for phoneme in phoneme_payloads:
            pronunciation = phoneme.get("PronunciationAssessment", {})
            items.append(
                PhonemeFeedback(
                    phoneme=phoneme.get("Phoneme", ""),
                    ipa=self._arpabet_phone_to_ipa(phoneme.get("Phoneme", "")) or None,
                    accuracy_score=float(pronunciation.get("AccuracyScore", 0)),
                    offset_ms=int(phoneme.get("Offset", 0) / 10000),
                    duration_ms=int(phoneme.get("Duration", 0) / 10000),
                    error_type=pronunciation.get("ErrorType", "None"),
                )
            )
        return items

    def _build_syllable_details(
        self,
        syllable_payloads: list[dict[str, Any]],
        phoneme_details: list[PhonemeFeedback],
    ) -> list[SyllableFeedback]:
        items: list[SyllableFeedback] = []
        for syllable in syllable_payloads:
            pronunciation = syllable.get("PronunciationAssessment", {})
            offset_ms = int(syllable.get("Offset", 0) / 10000)
            duration_ms = int(syllable.get("Duration", 0) / 10000)
            syllable_phonemes = [
                item
                for item in phoneme_details
                if item.offset_ms >= offset_ms and item.offset_ms <= offset_ms + duration_ms
            ]
            items.append(
                SyllableFeedback(
                    syllable=syllable.get("Syllable", syllable.get("SyllableText", "")),
                    grapheme=syllable.get("Grapheme"),
                    accuracy_score=float(pronunciation.get("AccuracyScore", 0)),
                    offset_ms=offset_ms,
                    duration_ms=duration_ms,
                    stress_level=pronunciation.get("Stress"),
                    phonemes=syllable_phonemes,
                )
            )
        return items

    async def _compose_response(self, raw: RawAssessment) -> AssessmentResponse:
        top_words = self._prioritize_words(raw.word_feedback)
        metrics = self._metric_insights(raw)
        llm_bundle = await self._generate_llm_bundle(raw, top_words, metrics)
        if llm_bundle:
            self._apply_word_overrides(raw.word_feedback, llm_bundle.get("word_overrides"))
            logger.warning("LLM_PATH_SELECTED %s", json.dumps({"used": True, "provider_mode": raw.provider_mode}))
            return self._response_from_llm(raw, top_words, metrics, llm_bundle)
        logger.warning("LLM_PATH_SELECTED %s", json.dumps({"used": False, "provider_mode": raw.provider_mode}))

        overview = self._fallback_overview(raw, top_words)
        coach_summary = self._fallback_summary(raw, top_words)
        top_issues = self._fallback_top_issues(top_words)
        practice_plan = self._fallback_practice_plan(raw, top_words)
        insights = self._fallback_insights(raw, top_words)

        return AssessmentResponse(
            overall_score=raw.overall_score,
            accuracy_score=raw.accuracy_score,
            fluency_score=raw.fluency_score,
            prosody_score=raw.prosody_score,
            completeness_score=raw.completeness_score,
            duration_seconds=raw.duration_seconds,
            transcript=raw.transcript,
            summary=coach_summary.summary,
            coaching=coach_summary.advice,
            word_feedback=raw.word_feedback,
            top_issues=top_issues,
            overview=overview,
            coach_summary=coach_summary,
            practice_plan=practice_plan,
            metrics=metrics,
            insights=insights,
            provider_mode=raw.provider_mode,  # type: ignore[arg-type]
            raw_azure_json=raw.raw_azure_json,
            azure_diagnostics=raw.azure_diagnostics,
        )

    def _response_from_llm(
        self,
        raw: RawAssessment,
        top_words: list[WordFeedback],
        metrics: list[MetricInsight],
        llm_bundle: dict[str, Any],
    ) -> AssessmentResponse:
        overview = self._llm_overview(raw, llm_bundle.get("overview"))
        coach_summary = self._llm_summary(raw, top_words, llm_bundle.get("coach_summary"))
        top_issues = self._llm_top_issues(top_words, llm_bundle.get("top_issues"))
        practice_plan = self._llm_practice_plan(raw, top_words, llm_bundle.get("practice_plan"))
        insights = self._llm_insights(llm_bundle.get("insights"))

        return AssessmentResponse(
            overall_score=raw.overall_score,
            accuracy_score=raw.accuracy_score,
            fluency_score=raw.fluency_score,
            prosody_score=raw.prosody_score,
            completeness_score=raw.completeness_score,
            duration_seconds=raw.duration_seconds,
            transcript=raw.transcript,
            summary=coach_summary.summary,
            coaching=coach_summary.advice,
            word_feedback=raw.word_feedback,
            top_issues=top_issues,
            overview=overview,
            coach_summary=coach_summary,
            practice_plan=practice_plan,
            metrics=metrics,
            insights=insights,
            provider_mode=raw.provider_mode,  # type: ignore[arg-type]
            raw_azure_json=raw.raw_azure_json,
            azure_diagnostics=raw.azure_diagnostics,
        )

    async def _generate_llm_bundle(
        self,
        raw: RawAssessment,
        top_words: list[WordFeedback],
        metrics: list[MetricInsight],
    ) -> dict[str, Any] | None:
        if not settings.groq_api_key or not raw.azure_diagnostics:
            return self._build_local_llm_bundle(raw, top_words, metrics)

        evidence_payload = {
            "transcript": raw.transcript,
            "scores": {
                "overall": raw.overall_score,
                "accuracy": raw.accuracy_score,
                "fluency": raw.fluency_score,
                "prosody": raw.prosody_score,
                "completeness": raw.completeness_score,
                "duration_seconds": raw.duration_seconds,
            },
            "metrics": [metric.model_dump() for metric in metrics],
            "patterns": raw.azure_diagnostics.patterns,
            "diagnostics_summary": {
                "reference_text_used": raw.azure_diagnostics.reference_text_used,
                "recognized_text": raw.azure_diagnostics.recognized_text,
                "overall_scores": raw.azure_diagnostics.overall_scores,
                "prosody": raw.azure_diagnostics.prosody,
                "flagged_word_count": raw.azure_diagnostics.flagged_word_count,
                "issue_category_counts": raw.azure_diagnostics.issue_category_counts,
                "segment_count": raw.azure_diagnostics.segment_count,
                "word_count": raw.azure_diagnostics.word_count,
                "patterns": raw.azure_diagnostics.patterns,
                "assessment_metadata": raw.azure_diagnostics.assessment_metadata,
                "segments": raw.azure_diagnostics.segments[:8],
            },
            "word_evidence": [self._llm_word_evidence(word) for word in raw.word_feedback[:24]],
            "priority_candidates": [self._llm_word_evidence(word) for word in top_words[:8]],
        }

        prompt = (
            "You are an IELTS pronunciation examiner, an English speech coach, and an accent-reduction tutor.\n"
            "Reason only from the structured pronunciation evidence provided.\n"
            "The backend has already normalized timing, phoneme, syllable, stress, and segment data. Treat that evidence as the source of truth.\n"
            "Do not invent phonemes, stress errors, timing issues, or coaching claims that are not grounded in the data.\n"
            "If the evidence is thin, be brief and conservative.\n"
            "Your goal is to maximize the learner's next score increase by identifying root causes rather than commenting on every word.\n"
            "Return strict JSON only with keys: overview, coach_summary, top_issues, practice_plan, insights, word_overrides.\n"
            "Task:\n"
            "1. Detect the pronunciation patterns producing the largest deduction.\n"
            "2. Rank them by learning impact.\n"
            "3. Ignore isolated low-impact mistakes.\n"
            "4. Build today's lesson.\n"
            "5. Build tomorrow's lesson.\n"
            "6. Explain every recommendation using only the evidence.\n"
            "Requirements:\n"
            "- Generate all coaching text from evidence, not from templates.\n"
            "- Keep the coach_summary under 120 words total.\n"
            "- Make each top issue distinct and tied to real evidence.\n"
            "- word_overrides must use an existing word and start_ms.\n"
            "- Only create word_overrides for words that genuinely need explanation.\n"
            "- Practice sentences must sound natural and use the recording's vocabulary or topic where possible.\n"
            "- Never mention Azure, APIs, dashboards, or product language.\n"
            "- Never produce CEFR estimates.\n"
            "- Do not invent exact improvement scores. If needed, describe likely improvement qualitatively.\n"
            "- When confidence is limited, say that the word needs another careful listen rather than pretending certainty.\n"
            "- Every word explanation should mention the specific syllable, phoneme, stress, rhythm, or omission evidence when available.\n"
            "JSON shape guidance:\n"
            "{"
            "\"overview\":{\"headline\":\"90/100\",\"level_label\":\"Strong pronunciation\",\"why\":\"...\",\"cefr_estimate\":\"\",\"confidence_label\":\"High confidence\",\"improvement_potential\":\"...\",\"celebration\":\"...\"},"
            "\"coach_summary\":{\"summary\":\"...\",\"strengths\":[\"...\"],\"weaknesses\":[\"...\"],\"speaking_habits\":[\"...\"],\"repeated_issue\":\"...\",\"advice\":\"...\"},"
            "\"top_issues\":[{\"word\":\"...\",\"score\":70,\"why\":\"...\",\"likely_issue\":\"...\",\"practice_tip\":\"...\",\"drill\":\"...\",\"difficulty\":\"medium\",\"priority\":\"high\",\"confidence\":\"high\"}],"
            "\"practice_plan\":{\"today_focus\":\"...\",\"estimated_score_if_fixed\":0,\"estimated_gain\":0,\"words\":[{\"word\":\"...\",\"reason\":\"...\",\"drill\":\"...\",\"syllable_hint\":\"...\",\"repetitions\":5,\"estimated_gain\":0}],\"sentences\":[{\"sentence\":\"...\",\"focus_words\":[\"...\"]}]},"
            "\"insights\":[{\"title\":\"...\",\"value\":\"...\",\"description\":\"...\"}],"
            "\"word_overrides\":[{\"word\":\"...\",\"start_ms\":0,\"issue\":\"...\",\"suggestion\":\"...\",\"confidence\":\"high\",\"pronunciation_explanation\":\"...\",\"affected_phonemes\":[\"...\"],\"affected_syllable\":\"...\",\"detected_issue_categories\":[\"...\"],\"evidence_summary\":\"...\"}]"
            "}\n"
            f"Evidence:\n{json.dumps(evidence_payload, ensure_ascii=True)}"
        )

        logger.warning(
            "Sending %s normalized words and %s priority candidates to Groq for reasoning.",
            len(evidence_payload["word_evidence"]),
            len(evidence_payload["priority_candidates"]),
        )
        logger.warning("LLM_PROMPT %s", prompt)

        try:
            async with httpx.AsyncClient(timeout=45) as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                    json={
                        "model": settings.groq_model,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {
                                "role": "system",
                                "content": "Return strict JSON only. Ground every sentence in the supplied pronunciation evidence.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                    },
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                logger.warning("LLM_RAW_RESPONSE %s", content)
                parsed = json.loads(content)
                logger.warning("LLM_PARSED_JSON %s", json.dumps(parsed))
                if not self._valid_llm_bundle(parsed):
                    logger.warning("LLM_VALIDATION_FAILED %s", json.dumps(parsed))
                    return self._build_local_llm_bundle(raw, top_words, metrics)
                return parsed
        except httpx.HTTPStatusError as exc:
            body = exc.response.text if exc.response is not None else ""
            logger.warning(
                "Groq reasoning failed; using local evidence-based coaching bundle. Status: %s Body: %s",
                exc.response.status_code if exc.response is not None else "unknown",
                body,
            )
            return self._build_local_llm_bundle(raw, top_words, metrics)
        except Exception as exc:
            logger.warning("Groq reasoning failed; using local evidence-based coaching bundle. Error: %s", exc)
            return self._build_local_llm_bundle(raw, top_words, metrics)

    def _llm_word_evidence(self, word: WordFeedback) -> dict[str, Any]:
        return {
            "word": word.word,
            "score": word.score,
            "status": word.status,
            "error_type": word.error_type,
            "confidence": word.confidence,
            "practice_priority": word.practice_priority,
            "start_ms": word.start_ms,
            "end_ms": word.end_ms,
            "duration_ms": word.duration_ms,
            "ipa": word.ipa,
            "syllables": word.syllables,
            "stress_syllable": word.stress_syllable,
            "native_pronunciation": word.native_pronunciation,
            "slow_pronunciation": word.slow_pronunciation,
            "affected_phonemes": word.affected_phonemes,
            "affected_syllable": word.affected_syllable,
            "pronunciation_explanation": word.pronunciation_explanation,
            "detected_issue_categories": word.detected_issue_categories,
            "azure_confidence_score": word.azure_confidence_score,
            "prosody_score": word.prosody_score,
            "syllable_accuracy_score": word.syllable_accuracy_score,
            "completeness_score": word.completeness_score,
            "expected_stress_pattern": word.expected_stress_pattern,
            "detected_stress_pattern": word.detected_stress_pattern,
            "phoneme_details": [item.model_dump() for item in word.phoneme_details],
            "syllable_details": [
                {
                    "syllable": item.syllable,
                    "grapheme": item.grapheme,
                    "accuracy_score": item.accuracy_score,
                    "offset_ms": item.offset_ms,
                    "duration_ms": item.duration_ms,
                    "stress_level": item.stress_level,
                    "phonemes": [phoneme.model_dump() for phoneme in item.phonemes],
                }
                for item in word.syllable_details
            ],
            "raw_breakdown": word.raw_breakdown,
        }

    def _build_local_llm_bundle(
        self,
        raw: RawAssessment,
        top_words: list[WordFeedback],
        metrics: list[MetricInsight],
    ) -> dict[str, Any]:
        evidence_patterns = raw.azure_diagnostics.patterns if raw.azure_diagnostics else []
        focus_words = top_words[:4]
        summary_text = self._build_local_summary(raw, focus_words)
        strengths = [self._strength_from_metrics(raw)]
        weaknesses = [self._weakness_from_word(word) for word in focus_words[:2]] or [
            f"{focus_words[0].word} needs steadier articulation and stress if you want a bigger score jump." if focus_words else "A few weaker words are creating most of the deduction."
        ]
        speaking_habits = [self._speaking_habit(raw, focus_words)]
        repeated_issue = self._repeated_issue(raw, focus_words)
        overview = {
            "headline": f"{round(raw.overall_score)}/100",
            "level_label": self._level_label(raw.overall_score),
            "why": evidence_patterns[0]
            if evidence_patterns
            else f"Most deductions came from {', '.join(word.word for word in focus_words[:3])}.",
            "confidence_label": self._confidence_label(raw),
            "improvement_potential": "Target the weakest words first and keep your rhythm steady while repeating them.",
            "celebration": "Your overall clarity is already strong; a small number of words can lift this score quickly.",
        }
        coach_summary = {
            "summary": summary_text,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "speaking_habits": speaking_habits,
            "repeated_issue": repeated_issue,
            "advice": "Practice the weakest words in isolation, then return to them inside full sentences from your recording.",
        }
        top_issues: list[dict[str, Any]] = []
        for word in focus_words:
            issue_text = word.evidence_summary or self._fallback_word_issue(
                word.word,
                word.error_type,
                word.affected_phonemes,
                word.affected_syllable,
                word.score,
            )
            practice_tip = word.suggestion or self._fallback_word_tip(
                word.word,
                word.error_type,
                word.affected_phonemes,
                word.affected_syllable,
            )
            top_issues.append(
                {
                    "word": word.word,
                    "score": word.score,
                    "why": issue_text,
                    "likely_issue": ", ".join(word.detected_issue_categories) or word.error_type or "clarity",
                    "practice_tip": practice_tip,
                    "drill": self._drill_for_word(word),
                    "difficulty": "hard" if word.score < 65 else "medium" if word.score < 80 else "easy",
                    "priority": word.practice_priority,
                    "confidence": word.confidence,
                    "start_ms": word.start_ms,
                    "score_if_fixed": 0,
                }
            )

        practice_sentences = self._practice_sentences(raw.transcript, focus_words)
        practice_plan = {
            "today_focus": self._practice_focus(focus_words),
            "estimated_score_if_fixed": 0,
            "estimated_gain": 0,
            "words": [
                {
                    "word": word.word,
                    "reason": word.evidence_summary or self._fallback_word_issue(
                        word.word,
                        word.error_type,
                        word.affected_phonemes,
                        word.affected_syllable,
                        word.score,
                    ),
                    "drill": self._drill_for_word(word),
                    "syllable_hint": " - ".join(word.syllables) if word.syllables else word.word,
                    "repetitions": 5,
                    "estimated_gain": 0,
                }
                for word in focus_words
            ],
            "sentences": [
                {
                    "sentence": sentence.sentence,
                    "focus_words": sentence.focus_words or [word.word],
                }
                for sentence, word in zip(practice_sentences, focus_words)
            ],
        }
        insights = [
            {"title": "Focus", "value": str(len(focus_words)), "description": "The biggest gains are likely to come from a small set of weaker words."},
            {"title": "Pattern", "value": "Detected", "description": evidence_patterns[0] if evidence_patterns else "The score drop is concentrated in a few weak words."},
        ]
        word_overrides = []
        for word in focus_words:
            word_overrides.append(
                {
                    "word": word.word,
                    "start_ms": word.start_ms,
                    "issue": self._fallback_word_issue(
                        word.word,
                        word.error_type,
                        word.affected_phonemes,
                        word.affected_syllable,
                        word.score,
                    ),
                    "suggestion": self._fallback_word_tip(
                        word.word,
                        word.error_type,
                        word.affected_phonemes,
                        word.affected_syllable,
                    ),
                    "confidence": word.confidence,
                    "pronunciation_explanation": word.evidence_summary or self._fallback_word_issue(
                        word.word,
                        word.error_type,
                        word.affected_phonemes,
                        word.affected_syllable,
                        word.score,
                    ),
                    "affected_phonemes": word.affected_phonemes,
                    "affected_syllable": word.affected_syllable,
                    "detected_issue_categories": word.detected_issue_categories,
                    "evidence_summary": word.evidence_summary or self._fallback_word_issue(
                        word.word,
                        word.error_type,
                        word.affected_phonemes,
                        word.affected_syllable,
                        word.score,
                    ),
                }
            )

        bundle = {
            "overview": overview,
            "coach_summary": coach_summary,
            "top_issues": top_issues,
            "practice_plan": practice_plan,
            "insights": insights,
            "word_overrides": word_overrides,
        }
        logger.warning("LLM_RAW_RESPONSE %s", json.dumps(bundle, ensure_ascii=True))
        logger.warning("LLM_PARSED_JSON %s", json.dumps(bundle, ensure_ascii=True))
        return bundle

    def _build_local_summary(self, raw: RawAssessment, top_words: list[WordFeedback]) -> str:
        focus_words = ", ".join(word.word for word in top_words[:3])
        if not focus_words:
            return "The recording shows a few small pronunciation issues that are worth practicing carefully."
        return (
            f"Your strongest points are clear overall, but {focus_words} are the main words dragging the score down. "
            "Targeting them with focused repetition should raise the score faster than repeating the whole sample."
        )

    def _valid_llm_bundle(self, payload: dict[str, Any]) -> bool:
        required_keys = {"overview", "coach_summary", "top_issues", "practice_plan", "insights", "word_overrides"}
        if not isinstance(payload, dict) or not required_keys.issubset(payload.keys()):
            return False
        if not isinstance(payload.get("overview"), dict):
            return False
        if not isinstance(payload.get("coach_summary"), dict):
            return False
        if not isinstance(payload.get("top_issues"), list):
            return False
        if not isinstance(payload.get("practice_plan"), dict):
            return False
        if not isinstance(payload.get("insights"), list):
            return False
        if not isinstance(payload.get("word_overrides"), list):
            return False
        return True

    async def _mock_assessment(self, inputs: ProviderInputs) -> RawAssessment:
        transcript = inputs.reference_text.strip() or (
            "I work on AI products and I want my pronunciation to sound clear, natural, and steady in conversation."
        )
        words = transcript.replace("\n", " ").split()
        seed = int(hashlib.sha256(f"{transcript}|{inputs.duration_seconds}".encode("utf-8")).hexdigest()[:8], 16)
        word_feedback: list[WordFeedback] = []
        total = 0.0

        for index, token in enumerate(words[:80]):
            word = token.strip(".,!?")
            if not word:
                continue
            base = 61 + ((seed >> (index % 8)) % 36)
            score = float(min(98, max(48, base - (8 if index % 6 == 0 else 0))))
            meta = self._word_pronunciation_meta(word)
            status_label = self._status_from_score(score)
            total += score
            issue_categories = ["mock"]
            word_feedback.append(
                WordFeedback(
                    word=word,
                    score=score,
                    status=status_label,
                    issue="",
                    suggestion="",
                    start_ms=index * 520,
                    end_ms=(index + 1) * 520,
                    duration_ms=520,
                    error_type="Mispronunciation" if status_label in {"watch", "needs-practice"} else "None",
                    confidence="medium",
                    phoneme_hint=None,
                    practice_priority=self._priority_from_score(score),
                    ipa=meta["ipa"],
                    syllables=meta["syllables"],
                    stress_syllable=meta["stress_syllable"],
                    native_pronunciation=meta["native_pronunciation"],
                    slow_pronunciation=meta["slow_pronunciation"],
                    affected_phonemes=[],
                    detected_issue_categories=issue_categories,
                    azure_confidence_score=score,
                    evidence_summary="Mock mode does not include phoneme or syllable diagnostics.",
                    expected_stress_pattern=meta["expected_stress_pattern"],
                    detected_stress_pattern=None,
                    raw_breakdown={"mock": True},
                )
            )

        overall = round(total / max(len(word_feedback), 1), 1)
        diagnostics = AzureDiagnosticsSummary(
            reference_text_used=transcript,
            recognized_text=transcript,
            overall_scores={
                "overall": overall,
                "accuracy": round(min(100, overall + 2.8), 1),
                "fluency": round(max(55, overall - 2), 1),
                "prosody": round(max(50, overall - 3.5), 1),
                "completeness": round(min(100, overall + 4), 1),
            },
            prosody={},
            flagged_word_count=len([word for word in word_feedback if word.status in {"watch", "needs-practice"}]),
            issue_category_counts={"mock": len(word_feedback)},
            segment_count=1,
            word_count=len(word_feedback),
            patterns=["Mock analysis is enabled, so coaching is illustrative rather than evidence-based."],
            assessment_metadata={"mode": "mock"},
            flagged_words=[self._compact_word_for_diagnostics(word) for word in self._prioritize_words(word_feedback)],
            transcript_words=[self._compact_word_for_diagnostics(word) for word in word_feedback],
            segments=[],
        )
        return RawAssessment(
            overall_score=overall,
            accuracy_score=diagnostics.overall_scores["accuracy"],
            fluency_score=diagnostics.overall_scores["fluency"],
            prosody_score=diagnostics.overall_scores["prosody"],
            completeness_score=diagnostics.overall_scores["completeness"],
            duration_seconds=inputs.duration_seconds,
            transcript=transcript,
            word_feedback=word_feedback,
            provider_mode="mock",
            raw_azure_json=None,
            azure_diagnostics=diagnostics,
        )

    def _aggregate_scores(self, scores: list[dict[str, float]], words: list[WordFeedback]) -> dict[str, float]:
        if scores:
            accuracy = round(sum(item["accuracy"] for item in scores) / len(scores), 1)
            fluency = round(sum(item["fluency"] for item in scores) / len(scores), 1)
            prosody = round(sum(item["prosody"] for item in scores) / len(scores), 1)
            completeness = round(sum(item["completeness"] for item in scores) / len(scores), 1)
        else:
            accuracy = round(sum(word.score for word in words) / max(len(words), 1), 1)
            fluency = accuracy
            prosody = max(50.0, accuracy - 4)
            completeness = min(100.0, accuracy + 4)
        overall = round((accuracy * 0.45) + (fluency * 0.2) + (prosody * 0.2) + (completeness * 0.15), 1)
        return {
            "overall": overall,
            "accuracy": accuracy,
            "fluency": fluency,
            "prosody": prosody,
            "completeness": completeness,
        }

    def _build_azure_diagnostics(
        self,
        word_feedback: list[WordFeedback],
        reference_text: str,
        recognized_text: str,
        scores: dict[str, float],
        raw_segments: list[dict[str, Any]],
    ) -> AzureDiagnosticsSummary:
        issue_counter = Counter()
        prosody_values: list[float] = []
        segment_diagnostics = [self._normalize_segment(segment) for segment in raw_segments]
        transcript_words = [self._compact_word_for_diagnostics(word) for word in word_feedback]
        flagged_words = [self._compact_word_for_diagnostics(word) for word in self._prioritize_words(word_feedback)]

        for word in word_feedback:
            for category in word.detected_issue_categories:
                issue_counter[category] += 1
            if word.prosody_score is not None:
                prosody_values.append(word.prosody_score)

        patterns = self._patterns_from_issue_counts(issue_counter, word_feedback)
        total_duration_ms = sum(word.duration_ms for word in word_feedback)

        return AzureDiagnosticsSummary(
            reference_text_used=reference_text,
            recognized_text=recognized_text,
            overall_scores=scores,
            prosody={
                "average_prosody_score": round(sum(prosody_values) / len(prosody_values), 1) if prosody_values else None,
                "segment_prosody_scores": [
                    segment.get("pronunciation_assessment", {}).get("prosody_score")
                    for segment in segment_diagnostics
                    if segment.get("pronunciation_assessment", {}).get("prosody_score") is not None
                ],
            },
            flagged_word_count=len([item for item in word_feedback if item.status in {"watch", "needs-practice"}]),
            issue_category_counts=dict(issue_counter),
            segment_count=len(raw_segments),
            word_count=len(word_feedback),
            patterns=patterns,
            assessment_metadata={
                "total_duration_ms": total_duration_ms,
                "reference_word_count": len(reference_text.split()),
                "recognized_word_count": len(word_feedback),
            },
            flagged_words=flagged_words,
            transcript_words=transcript_words,
            segments=segment_diagnostics,
        )

    def _normalize_segment(self, segment: dict[str, Any]) -> dict[str, Any]:
        nbest = segment.get("NBest", [{}])[0]
        pa = nbest.get("PronunciationAssessment", {})
        return {
            "text": segment.get("DisplayText") or nbest.get("Display") or nbest.get("Lexical"),
            "duration_ms": int(segment.get("Duration", 0) / 10000),
            "offset_ms": int(segment.get("Offset", 0) / 10000),
            "confidence": nbest.get("Confidence"),
            "pronunciation_assessment": {
                "accuracy_score": self._optional_float(pa.get("AccuracyScore")),
                "fluency_score": self._optional_float(pa.get("FluencyScore")),
                "prosody_score": self._optional_float(pa.get("ProsodyScore")),
                "completeness_score": self._optional_float(pa.get("CompletenessScore")),
            },
            "words": [
                {
                    "word": word.get("Word"),
                    "offset_ms": int(word.get("Offset", 0) / 10000),
                    "duration_ms": int(word.get("Duration", 0) / 10000),
                    "pronunciation_assessment": {
                        "accuracy_score": self._optional_float(word.get("PronunciationAssessment", {}).get("AccuracyScore")),
                        "error_type": word.get("PronunciationAssessment", {}).get("ErrorType", "None"),
                        "prosody_score": self._optional_float(word.get("PronunciationAssessment", {}).get("ProsodyScore")),
                        "syllable_score": self._optional_float(word.get("PronunciationAssessment", {}).get("SyllableScore")),
                    },
                    "phonemes": [
                        {
                            "phoneme": phoneme.get("Phoneme"),
                            "accuracy_score": self._optional_float(phoneme.get("PronunciationAssessment", {}).get("AccuracyScore")),
                            "error_type": phoneme.get("PronunciationAssessment", {}).get("ErrorType", "None"),
                            "offset_ms": int(phoneme.get("Offset", 0) / 10000),
                            "duration_ms": int(phoneme.get("Duration", 0) / 10000),
                        }
                        for phoneme in word.get("Phonemes", [])
                    ],
                    "syllables": [
                        {
                            "syllable": syllable.get("Syllable", syllable.get("SyllableText", "")),
                            "grapheme": syllable.get("Grapheme"),
                            "accuracy_score": self._optional_float(syllable.get("PronunciationAssessment", {}).get("AccuracyScore")),
                            "stress": syllable.get("PronunciationAssessment", {}).get("Stress"),
                            "offset_ms": int(syllable.get("Offset", 0) / 10000),
                            "duration_ms": int(syllable.get("Duration", 0) / 10000),
                        }
                        for syllable in word.get("Syllables", [])
                    ],
                }
                for word in nbest.get("Words", [])
            ],
        }

    def _compact_word_for_diagnostics(self, word: WordFeedback) -> dict[str, Any]:
        return {
            "word": word.word,
            "score": word.score,
            "status": word.status,
            "error_type": word.error_type,
            "confidence": word.confidence,
            "start_ms": word.start_ms,
            "end_ms": word.end_ms,
            "duration_ms": word.duration_ms,
            "issue_categories": word.detected_issue_categories,
            "affected_phonemes": word.affected_phonemes,
            "affected_syllable": word.affected_syllable,
            "phoneme_details": [item.model_dump() for item in word.phoneme_details],
            "syllable_details": [item.model_dump() for item in word.syllable_details],
            "evidence_summary": word.evidence_summary,
            "prosody_score": word.prosody_score,
            "syllable_accuracy_score": word.syllable_accuracy_score,
            "expected_stress_pattern": word.expected_stress_pattern,
            "detected_stress_pattern": word.detected_stress_pattern,
        }

    def _compact_word_for_llm(self, word: WordFeedback) -> dict[str, Any]:
        payload = self._compact_word_for_diagnostics(word)
        payload.update(
            {
                "ipa": word.ipa,
                "syllables": word.syllables,
                "stress_syllable": word.stress_syllable,
                "native_pronunciation": word.native_pronunciation,
                "slow_pronunciation": word.slow_pronunciation,
                "raw_breakdown": word.raw_breakdown,
            }
        )
        return payload

    def _prioritize_words(self, words: list[WordFeedback]) -> list[WordFeedback]:
        flagged = [word for word in words if word.status in {"watch", "needs-practice"}]
        if not flagged:
            flagged = sorted(words, key=lambda word: word.score)[:5]
        return sorted(
            flagged,
            key=lambda word: (
                0 if word.practice_priority == "high" else 1 if word.practice_priority == "medium" else 2,
                word.score,
                word.start_ms,
            ),
        )[:5]

    def _metric_insights(self, raw: RawAssessment) -> list[MetricInsight]:
        patterns = raw.azure_diagnostics.patterns if raw.azure_diagnostics else []
        main_pattern = patterns[0] if patterns else "The main deductions were concentrated in a small number of words."
        return [
            MetricInsight(
                key="overall",
                label="Overall",
                score=raw.overall_score,
                band=self._band(raw.overall_score),
                explanation=main_pattern,
            ),
            MetricInsight(
                key="accuracy",
                label="Accuracy",
                score=raw.accuracy_score,
                band=self._band(raw.accuracy_score),
                explanation="This reflects how closely the spoken word forms matched the expected pronunciation.",
            ),
            MetricInsight(
                key="prosody",
                label="Prosody",
                score=raw.prosody_score,
                band=self._band(raw.prosody_score),
                explanation="This reflects sentence rhythm, stress placement, and how natural the delivery sounded.",
            ),
            MetricInsight(
                key="fluency",
                label="Fluency",
                score=raw.fluency_score,
                band=self._band(raw.fluency_score),
                explanation="This reflects continuity of speech and whether pauses disrupted the flow.",
            ),
            MetricInsight(
                key="completeness",
                label="Completeness",
                score=raw.completeness_score,
                band=self._band(raw.completeness_score),
                explanation="This reflects how much of the intended spoken content was captured clearly.",
            ),
        ]

    def _fallback_overview(self, raw: RawAssessment, top_words: list[WordFeedback]) -> CoachOverview:
        focus_words = ", ".join(word.word for word in top_words[:4]) or "a few lower-scoring words"
        pattern = raw.azure_diagnostics.patterns[0] if raw.azure_diagnostics and raw.azure_diagnostics.patterns else ""
        return CoachOverview(
            headline=f"{round(raw.overall_score)}/100",
            level_label=self._level_label(raw.overall_score),
            why=pattern or f"Most of the score drop came from {focus_words}.",
            cefr_estimate="",
            confidence_label=self._confidence_label(raw),
            improvement_potential="Target the weakest words first rather than repeating the whole recording.",
            celebration="A small set of words is creating most of the deduction.",
        )

    def _fallback_summary(self, raw: RawAssessment, top_words: list[WordFeedback]) -> CoachSummary:
        strengths = [self._strength_from_metrics(raw)]
        weaknesses = [self._weakness_from_word(word) for word in top_words[:2]]
        speaking_habits = [self._speaking_habit(raw, top_words)]
        repeated_issue = self._repeated_issue(raw, top_words)
        advice = "Practice the weakest words in isolation, then say them again inside full sentences from your recording."
        summary = " ".join(
            [
                strengths[0],
                weaknesses[0] if weaknesses else "A few words need more precise articulation.",
                advice,
            ]
        )
        return CoachSummary(
            summary=summary[:320],
            strengths=strengths,
            weaknesses=weaknesses or ["A few words lost clarity compared with the rest of the sample."],
            speaking_habits=speaking_habits,
            repeated_issue=repeated_issue,
            advice=advice,
        )

    def _fallback_top_issues(self, top_words: list[WordFeedback]) -> list[PriorityIssue]:
        issues: list[PriorityIssue] = []
        for word in top_words:
            issues.append(
                PriorityIssue(
                    word=word.word,
                    score=word.score,
                    why=word.evidence_summary or word.issue,
                    likely_issue=", ".join(word.detected_issue_categories) or word.error_type or "clarity",
                    practice_tip=word.suggestion,
                    drill=self._drill_for_word(word),
                    difficulty="hard" if word.score < 65 else "medium" if word.score < 80 else "easy",
                    priority=word.practice_priority,
                    confidence=word.confidence,
                    start_ms=word.start_ms,
                    end_ms=word.end_ms,
                    ipa=word.ipa,
                    syllables=word.syllables,
                    stress_syllable=word.stress_syllable,
                    native_pronunciation=word.native_pronunciation,
                    slow_pronunciation=word.slow_pronunciation,
                )
            )
        return issues

    def _fallback_practice_plan(self, raw: RawAssessment, top_words: list[WordFeedback]) -> PracticePlan:
        practice_words = [
            PracticeWord(
                word=word.word,
                reason=word.evidence_summary or word.issue,
                drill=self._drill_for_word(word),
                syllable_hint=" - ".join(word.syllables) if word.syllables else word.word,
                ipa=word.ipa,
                stress_syllable=word.stress_syllable,
                native_pronunciation=word.native_pronunciation,
                slow_pronunciation=word.slow_pronunciation,
                repetitions=5,
                estimated_gain=0,
            )
            for word in top_words
        ]
        return PracticePlan(
            today_focus=self._practice_focus(top_words),
            estimated_score_if_fixed=0,
            estimated_gain=0,
            words=practice_words,
            sentences=self._practice_sentences(raw.transcript, top_words),
        )

    def _fallback_insights(self, raw: RawAssessment, top_words: list[WordFeedback]) -> list[CoachInsight]:
        insights = [
            CoachInsight(
                title="Focus",
                value=str(len(top_words)),
                description="Only a handful of words are causing most of the deduction, so targeted practice will help more than repeating the whole passage.",
            )
        ]
        if raw.azure_diagnostics and raw.azure_diagnostics.patterns:
            insights.append(
                CoachInsight(
                    title="Pattern",
                    value="Detected",
                    description=raw.azure_diagnostics.patterns[0],
                )
            )
        return insights

    def _llm_overview(self, raw: RawAssessment, payload: dict[str, Any] | None) -> CoachOverview:
        if not payload:
            return self._fallback_overview(raw, self._prioritize_words(raw.word_feedback))
        return CoachOverview(
            headline=str(payload.get("headline") or f"{round(raw.overall_score)}/100"),
            level_label=str(payload.get("level_label") or self._level_label(raw.overall_score)),
            why=str(payload.get("why") or ""),
            cefr_estimate="",
            confidence_label=str(payload.get("confidence_label") or self._confidence_label(raw)),
            improvement_potential=str(payload.get("improvement_potential") or ""),
            celebration=str(payload.get("celebration") or ""),
        )

    def _llm_summary(
        self,
        raw: RawAssessment,
        top_words: list[WordFeedback],
        payload: dict[str, Any] | None,
    ) -> CoachSummary:
        if not payload:
            return self._fallback_summary(raw, top_words)
        strengths = [str(item) for item in payload.get("strengths", []) if str(item).strip()]
        weaknesses = [str(item) for item in payload.get("weaknesses", []) if str(item).strip()]
        speaking_habits = [str(item) for item in payload.get("speaking_habits", []) if str(item).strip()]
        return CoachSummary(
            summary=str(payload.get("summary") or ""),
            strengths=strengths,
            weaknesses=weaknesses,
            speaking_habits=speaking_habits,
            repeated_issue=str(payload.get("repeated_issue") or ""),
            advice=str(payload.get("advice") or ""),
        )

    def _llm_top_issues(self, top_words: list[WordFeedback], payload: list[dict[str, Any]] | None) -> list[PriorityIssue]:
        if not payload:
            return self._fallback_top_issues(top_words)
        indexed = {(word.word.lower(), word.start_ms): word for word in top_words}
        rendered: list[PriorityIssue] = []
        for item in payload[:5]:
            key = ((item.get("word") or "").lower(), int(item.get("start_ms", -1)))
            source = indexed.get(key) or next((word for word in top_words if word.word.lower() == key[0]), None)
            if not source:
                continue
            difficulty_value = str(item.get("difficulty") or "").strip().lower()
            if difficulty_value not in {"easy", "medium", "hard"}:
                if difficulty_value == "high":
                    difficulty_value = "hard"
                elif difficulty_value == "low":
                    difficulty_value = "easy"
                else:
                    difficulty_value = "hard" if source.score < 65 else "medium" if source.score < 80 else "easy"
            rendered.append(
                PriorityIssue(
                    word=source.word,
                    score=float(item.get("score", source.score)),
                    why=str(item.get("why") or source.evidence_summary or ""),
                    likely_issue=str(item.get("likely_issue") or ", ".join(source.detected_issue_categories) or source.error_type or ""),
                    practice_tip=str(item.get("practice_tip") or ""),
                    drill=str(item.get("drill") or ""),
                    difficulty=difficulty_value,
                    priority=str(item.get("priority") or source.practice_priority),
                    confidence=str(item.get("confidence") or source.confidence),
                    start_ms=source.start_ms,
                    end_ms=source.end_ms,
                    ipa=source.ipa,
                    syllables=source.syllables,
                    stress_syllable=source.stress_syllable,
                    native_pronunciation=source.native_pronunciation,
                    slow_pronunciation=source.slow_pronunciation,
                )
            )
        return rendered or self._fallback_top_issues(top_words)

    def _llm_practice_plan(
        self,
        raw: RawAssessment,
        top_words: list[WordFeedback],
        payload: dict[str, Any] | None,
    ) -> PracticePlan:
        if not payload:
            return self._fallback_practice_plan(raw, top_words)
        indexed = {(word.word.lower(), word.start_ms): word for word in raw.word_feedback}
        words: list[PracticeWord] = []
        for item in payload.get("words", [])[:5]:
            key = ((item.get("word") or "").lower(), int(item.get("start_ms", -1)))
            source = indexed.get(key) or next((word for word in top_words if word.word.lower() == key[0]), None)
            if not source:
                continue
            words.append(
                PracticeWord(
                    word=source.word,
                    reason=str(item.get("reason") or source.evidence_summary or ""),
                    drill=str(item.get("drill") or ""),
                    syllable_hint=str(item.get("syllable_hint") or " - ".join(source.syllables) or source.word),
                    ipa=source.ipa,
                    stress_syllable=source.stress_syllable,
                    native_pronunciation=source.native_pronunciation,
                    slow_pronunciation=source.slow_pronunciation,
                    repetitions=max(1, min(10, int(item.get("repetitions", 5)))),
                    estimated_gain=0,
                )
            )
        sentences: list[PracticeSentence] = []
        for item in payload.get("sentences", [])[:5]:
            sentence = str(item.get("sentence") or "").strip()
            focus_words = [str(word) for word in item.get("focus_words", []) if str(word).strip()]
            if sentence:
                sentences.append(PracticeSentence(sentence=sentence, focus_words=focus_words))
        return PracticePlan(
            today_focus=str(payload.get("today_focus") or ""),
            estimated_score_if_fixed=0,
            estimated_gain=0,
            words=words,
            sentences=sentences,
        )

    def _llm_insights(self, payload: list[dict[str, Any]] | None) -> list[CoachInsight]:
        if not payload:
            return []
        rendered: list[CoachInsight] = []
        for item in payload[:4]:
            title = str(item.get("title") or "").strip()
            value = str(item.get("value") or "").strip()
            description = str(item.get("description") or "").strip()
            if title and value and description:
                rendered.append(CoachInsight(title=title, value=value, description=description))
        return rendered

    def _apply_word_overrides(self, words: list[WordFeedback], overrides: list[dict[str, Any]] | None) -> None:
        if not overrides:
            return
        indexed_words = {(word.word.lower(), word.start_ms): word for word in words}
        for override in overrides:
            key = ((override.get("word") or "").lower(), int(override.get("start_ms", -1)))
            target = indexed_words.get(key)
            if not target:
                continue
            if override.get("issue"):
                target.issue = override["issue"]
            if override.get("suggestion"):
                target.suggestion = override["suggestion"]
            if override.get("confidence") in {"high", "medium", "low"}:
                target.confidence = override["confidence"]
            if override.get("pronunciation_explanation"):
                target.pronunciation_explanation = override["pronunciation_explanation"]
            if override.get("affected_phonemes"):
                target.affected_phonemes = override["affected_phonemes"]
            if override.get("affected_syllable"):
                target.affected_syllable = override["affected_syllable"]
            if override.get("detected_issue_categories"):
                target.detected_issue_categories = override["detected_issue_categories"]
            if override.get("evidence_summary"):
                target.evidence_summary = override["evidence_summary"]

    def _issue_categories(
        self,
        error_type: str,
        phonemes: list[PhonemeFeedback],
        syllables: list[SyllableFeedback],
        pronunciation: dict[str, Any],
    ) -> list[str]:
        categories: list[str] = []
        if error_type == "Omission":
            categories.append("omission")
        elif error_type == "Insertion":
            categories.append("insertion")
        elif error_type not in {"None", ""}:
            categories.append(error_type.lower())

        low_phonemes = [item for item in phonemes if item.accuracy_score < 75]
        low_syllables = [item for item in syllables if item.accuracy_score < 80]
        if low_phonemes:
            categories.append("phoneme articulation")
        if low_syllables:
            categories.append("syllable clarity")
        prosody_score = self._optional_float(pronunciation.get("ProsodyScore"))
        if prosody_score is not None and prosody_score < 80:
            categories.append("word stress")
        if low_phonemes and len(low_phonemes) >= 2:
            categories.append("sound sequence")
        return list(dict.fromkeys(categories))

    def _patterns_from_issue_counts(self, issue_counter: Counter, words: list[WordFeedback]) -> list[str]:
        patterns: list[str] = []
        flagged = [word for word in words if word.status in {"watch", "needs-practice"}]

        for category, count in issue_counter.most_common(3):
            if count <= 1:
                continue
            affected = list(dict.fromkeys(word.word for word in flagged if category in word.detected_issue_categories))[:3]
            context = f" — mainly in {', '.join(affected)}" if affected else ""
            if category == "word stress":
                patterns.append(f"Stress placement is creating deductions in several words{context}.")
            elif category == "phoneme articulation":
                patterns.append(f"Individual sounds are the main source of deduction{context}.")
            elif category == "syllable clarity":
                patterns.append(f"One weak syllable is driving the score down in several words{context}.")
            elif category == "omission":
                patterns.append(f"Parts of some words may have dropped out{context}.")
            elif category == "insertion":
                patterns.append(f"Some words may include extra sounds that were not expected{context}.")
            else:
                patterns.append(f"{category.capitalize()} is affecting several words{context}.")

        if not patterns and words:
            slow_words = [word.word for word in self._prioritize_words(words)[:3]]
            patterns.append(f"Most deductions are concentrated in {', '.join(slow_words)}.")
        return patterns

    def _evidence_summary(
        self,
        error_type: str,
        phonemes: list[PhonemeFeedback],
        syllables: list[SyllableFeedback],
        pronunciation: dict[str, Any],
    ) -> str:
        low_phonemes = [item for item in sorted(phonemes, key=lambda item: item.accuracy_score) if item.accuracy_score < 80][:3]
        weak_syllable = min(syllables, key=lambda item: item.accuracy_score) if syllables else None
        prosody_score = self._optional_float(pronunciation.get("ProsodyScore"))
        parts: list[str] = []
        if error_type == "Omission":
            parts.append("Part of this word may have dropped out during the recording.")
        elif error_type == "Insertion":
            parts.append("This word may include an extra sound that was not expected.")
        elif error_type not in {"None", ""}:
            parts.append(f"The assessment flagged this as a {error_type.lower()}.")
        if weak_syllable and weak_syllable.accuracy_score < 82:
            parts.append(f"The {weak_syllable.syllable} part was the least stable syllable here.")
        if low_phonemes:
            sound_list = ", ".join(item.phoneme for item in low_phonemes)
            if len(low_phonemes) == 1:
                parts.append(f"The {sound_list} sound scored below the expected threshold.")
            else:
                parts.append(f"The sounds {sound_list} were the weakest in this word.")
        if prosody_score is not None and prosody_score < 80:
            parts.append("The stress or rhythm on this word was less consistent than the stronger words.")
        return " ".join(parts) if parts else "This word was slightly less precise than your strongest pronunciations."

    def _fallback_word_issue(
        self,
        word: str,
        error_type: str,
        affected_phonemes: list[str],
        affected_syllable: str | None,
        score: float,
    ) -> str:
        if error_type == "Omission":
            return f"Part of {word} may have dropped out."
        if error_type == "Insertion":
            return f"{word} may include an extra sound."
        if affected_syllable and affected_phonemes:
            return f"The deduction in {word} centers on the {affected_syllable} syllable and the sounds {', '.join(affected_phonemes[:2])}."
        if affected_phonemes:
            return f"The weakest part of {word} was around {', '.join(affected_phonemes[:2])}."
        if score < 72:
            return f"{word} stood out as one of the less precise words in the sample."
        return f"{word} was understandable but less polished than your strongest words."

    def _fallback_word_tip(
        self,
        word: str,
        error_type: str,
        affected_phonemes: list[str],
        affected_syllable: str | None,
    ) -> str:
        if error_type == "Omission":
            return f"Slow down and make every part of {word} audible before speeding up again."
        if error_type == "Insertion":
            return f"Say {word} lightly and avoid adding an extra vowel or consonant between sounds."
        if affected_syllable:
            return f"Practice the {affected_syllable} syllable on its own, then reconnect it to the full word."
        if affected_phonemes:
            return f"Repeat {word} while exaggerating the sounds around {', '.join(affected_phonemes[:2])}."
        return f"Say {word} once slowly, once naturally, then place it back into a short phrase."

    def _drill_for_word(self, word: WordFeedback) -> str:
        if word.affected_syllable:
            return f"Hold the {word.affected_syllable} syllable slightly longer, then say the whole word three times."
        if word.affected_phonemes:
            return f"Alternate {word.word} with a slow version that emphasizes {', '.join(word.affected_phonemes[:2])}."
        return f"Repeat {word.word} slowly, then at normal speed, keeping the ending fully audible."

    def _practice_focus(self, top_words: list[WordFeedback]) -> str:
        if not top_words:
            return "Repeat the recording once more and listen for the least stable words."
        first = top_words[0]
        if "word stress" in first.detected_issue_categories:
            return "Start with stress placement on the weakest words before working on full-sentence rhythm."
        if "phoneme articulation" in first.detected_issue_categories:
            return "Start with the lowest-scoring sounds inside each weak word before practicing full sentences."
        return "Practice the weakest words in isolation first, then place them back into natural sentences."

    def _practice_sentences(self, transcript: str, top_words: list[WordFeedback]) -> list[PracticeSentence]:
        if not transcript:
            return []
        source_sentences = [item.strip() for item in transcript.replace("?", ".").replace("!", ".").split(".") if item.strip()]
        results: list[PracticeSentence] = []
        for word in top_words[:3]:
            matching = next((sentence for sentence in source_sentences if word.word.lower() in sentence.lower()), None)
            if matching:
                results.append(PracticeSentence(sentence=matching, focus_words=[word.word]))
            else:
                results.append(PracticeSentence(sentence=f"Say {word.word} clearly in a short natural sentence.", focus_words=[word.word]))
        return results

    def _strength_from_metrics(self, raw: RawAssessment) -> str:
        strongest = max(
            [
                ("accuracy", raw.accuracy_score),
                ("fluency", raw.fluency_score),
                ("prosody", raw.prosody_score),
                ("completeness", raw.completeness_score),
            ],
            key=lambda item: item[1],
        )
        mapping = {
            "accuracy": "Your word forms were mostly recognizable and stable.",
            "fluency": "Your flow stayed reasonably steady across the recording.",
            "prosody": "Your rhythm and emphasis were already fairly natural in many places.",
            "completeness": "Most of the spoken content came through clearly.",
        }
        return mapping[strongest[0]]

    def _weakness_from_word(self, word: WordFeedback) -> str:
        if word.affected_syllable:
            return f"{word.word} lost clarity around the {word.affected_syllable} syllable."
        if word.affected_phonemes:
            return f"{word.word} lost precision around {', '.join(word.affected_phonemes[:2])}."
        return f"{word.word} needs a more consistent pronunciation shape."

    def _speaking_habit(self, raw: RawAssessment, top_words: list[WordFeedback]) -> str:
        if raw.prosody_score < raw.accuracy_score - 6:
            return "Word recognition is stronger than sentence rhythm, so pacing and stress deserve extra attention."
        if any("word stress" in word.detected_issue_categories for word in top_words):
            return "The lower-scoring words suggest that stress placement shifts on harder vocabulary."
        return "Most deductions are clustered in a few difficult words rather than across the whole recording."

    def _repeated_issue(self, raw: RawAssessment, top_words: list[WordFeedback]) -> str:
        if raw.azure_diagnostics and raw.azure_diagnostics.issue_category_counts:
            category = max(raw.azure_diagnostics.issue_category_counts.items(), key=lambda item: item[1])[0]
            if category == "phoneme articulation":
                return "Individual sounds are the most consistent source of score loss."
            if category == "syllable clarity":
                return "One weak syllable often drives the deduction on the lower-scoring words."
            if category == "word stress":
                return "Stress placement is the most repeated weakness in this recording."
            return f"{category.capitalize()} appears most often across the weaker words."
        if top_words:
            return f"{top_words[0].word} is part of a small group of words causing most of the deduction."
        return "A small number of words are driving the overall score down."

    def _status_from_score(self, score: float) -> str:
        if score >= 92:
            return "excellent"
        if score >= 84:
            return "good"
        if score >= 72:
            return "watch"
        return "needs-practice"

    def _priority_from_score(self, score: float) -> str:
        if score < 68:
            return "high"
        if score < 82:
            return "medium"
        return "low"

    def _confidence_from_evidence(
        self,
        score: float,
        error_type: str,
        phonemes: list[PhonemeFeedback],
        syllables: list[SyllableFeedback],
    ) -> str:
        evidence_count = len([item for item in phonemes if item.accuracy_score < 80]) + len(
            [item for item in syllables if item.accuracy_score < 82]
        )
        if error_type not in {"None", ""}:
            evidence_count += 1
        if evidence_count >= 3:
            return "high"
        if evidence_count >= 1 or score < 75:
            return "medium"
        return "low"

    def _band(self, score: float) -> str:
        if score >= 90:
            return "Excellent"
        if score >= 82:
            return "Strong"
        if score >= 72:
            return "Developing"
        return "Needs work"

    def _level_label(self, score: float) -> str:
        if score >= 92:
            return "Excellent pronunciation"
        if score >= 84:
            return "Strong pronunciation"
        if score >= 74:
            return "Good foundation"
        return "Needs focused practice"

    def _confidence_label(self, raw: RawAssessment) -> str:
        if raw.azure_diagnostics and raw.azure_diagnostics.segment_count >= 1 and raw.completeness_score >= 85:
            return "High confidence"
        if raw.completeness_score >= 72:
            return "Medium confidence"
        return "Limited confidence"

    def _stress_pattern(self, syllables: list[SyllableFeedback]) -> str | None:
        if not syllables:
            return None
        rendered: list[str] = []
        for syllable in syllables:
            label = syllable.syllable or "?"
            if syllable.stress_level:
                rendered.append(f"{label}({syllable.stress_level})")
            else:
                rendered.append(label)
        return " / ".join(rendered) if rendered else None

    def _optional_float(self, value: Any) -> float | None:
        try:
            if value is None or value == "":
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def _word_pronunciation_meta(self, word: str) -> dict[str, Any]:
        clean = "".join(char for char in word.lower() if char.isalpha())
        fallback_syllables = self._heuristic_syllables(clean)
        fallback = {
            "ipa": None,
            "syllables": fallback_syllables,
            "stress_syllable": None,
            "native_pronunciation": word,
            "slow_pronunciation": " - ".join(fallback_syllables) if clean else word,
            "expected_stress_pattern": None,
        }
        if not clean:
            return fallback
        try:
            import pronouncing  # type: ignore[import-not-found]
        except ImportError:
            return fallback
        phones = pronouncing.phones_for_word(clean)
        if not phones:
            return fallback
        selected = phones[0]
        stresses = pronouncing.stresses(selected)
        split = self._syllabify_arpabet(selected.split())
        stress_syllable = next((index + 1 for index, digit in enumerate(stresses) if digit == "1"), None)
        return {
            "ipa": self._arpabet_to_ipa(selected),
            "syllables": split or fallback["syllables"],
            "stress_syllable": stress_syllable if stress_syllable and stress_syllable <= max(len(split), 1) else None,
            "native_pronunciation": word,
            "slow_pronunciation": " - ".join(split) if split else fallback["slow_pronunciation"],
            "expected_stress_pattern": stresses or None,
        }

    def _heuristic_syllables(self, word: str) -> list[str]:
        if not word:
            return []
        vowels = "aeiouy"
        pieces: list[str] = []
        current = ""
        seen_vowel = False
        for index, char in enumerate(word):
            current += char
            if char in vowels:
                seen_vowel = True
                next_char = word[index + 1] if index + 1 < len(word) else ""
                if next_char not in vowels:
                    pieces.append(current)
                    current = ""
        if current:
            if pieces:
                pieces[-1] += current
            else:
                pieces.append(current)
        return pieces if seen_vowel else [word]

    def _syllabify_arpabet(self, phones: list[str]) -> list[str]:
        syllables: list[list[str]] = []
        current: list[str] = []
        vowel_seen = False
        for phone in phones:
            current.append(phone)
            if any(char.isdigit() for char in phone):
                vowel_seen = True
            elif vowel_seen and phone in {"P", "T", "K", "B", "D", "G", "F", "V", "S", "Z", "SH", "CH", "JH", "M", "N", "NG", "L", "R"}:
                syllables.append(current[:-1] or current)
                current = [phone]
                vowel_seen = False
        if current:
            syllables.append(current)
        rendered: list[str] = []
        for syllable in syllables:
            text = "".join(self._arpabet_phone_to_ipa(phone) for phone in syllable if self._arpabet_phone_to_ipa(phone))
            if text:
                rendered.append(text)
        return rendered

    def _arpabet_to_ipa(self, phones: str) -> str:
        return "".join(self._arpabet_phone_to_ipa(phone) for phone in phones.split())

    def _arpabet_phone_to_ipa(self, phone: str) -> str:
        clean_phone = "".join(char for char in phone if not char.isdigit())
        return ARPABET_TO_IPA.get(clean_phone, "")
