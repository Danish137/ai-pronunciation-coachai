import hashlib
import json
import statistics
from dataclasses import dataclass

import httpx
from fastapi import HTTPException, status

from ..core.config import get_settings
from ..schemas.assessment import (
    AssessmentResponse,
    CoachInsight,
    CoachOverview,
    CoachSummary,
    MetricInsight,
    PracticePlan,
    PracticeSentence,
    PracticeWord,
    PriorityIssue,
    WordFeedback,
)

settings = get_settings()

ARPABET_TO_IPA = {
    "AA": "ɑ",
    "AE": "æ",
    "AH": "ʌ",
    "AO": "ɔ",
    "AW": "aʊ",
    "AY": "aɪ",
    "B": "b",
    "CH": "tʃ",
    "D": "d",
    "DH": "ð",
    "EH": "ɛ",
    "ER": "ɝ",
    "EY": "eɪ",
    "F": "f",
    "G": "ɡ",
    "HH": "h",
    "IH": "ɪ",
    "IY": "i",
    "JH": "dʒ",
    "K": "k",
    "L": "l",
    "M": "m",
    "N": "n",
    "NG": "ŋ",
    "OW": "oʊ",
    "OY": "ɔɪ",
    "P": "p",
    "R": "r",
    "S": "s",
    "SH": "ʃ",
    "T": "t",
    "TH": "θ",
    "UH": "ʊ",
    "UW": "u",
    "V": "v",
    "W": "w",
    "Y": "j",
    "Z": "z",
    "ZH": "ʒ",
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


class AssessmentService:
    async def analyze(self, inputs: ProviderInputs) -> AssessmentResponse:
        if settings.enable_mock_analysis or not (settings.azure_speech_key and settings.azure_speech_region):
            raw_assessment = await self._mock_assessment(inputs)
        else:
            raw_assessment = await self._azure_assessment(inputs)

        return await self._compose_response(raw_assessment)

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
        scores: list[dict[str, float]] = []
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
            nbest = raw_json.get("NBest", [{}])[0]
            pa = nbest.get("PronunciationAssessment", {})
            scores.append(
                {
                    "accuracy": float(pa.get("AccuracyScore", 0)),
                    "fluency": float(pa.get("FluencyScore", 0)),
                    "prosody": float(pa.get("ProsodyScore", 0)),
                    "completeness": float(pa.get("CompletenessScore", 0)),
                }
            )
            for word in nbest.get("Words", []):
                parsed_word = self._build_word_feedback(word)
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

        aggregate = self._aggregate_scores(scores, word_feedback)
        return RawAssessment(
            overall_score=aggregate["overall"],
            accuracy_score=aggregate["accuracy"],
            fluency_score=aggregate["fluency"],
            prosody_score=aggregate["prosody"],
            completeness_score=aggregate["completeness"],
            duration_seconds=inputs.duration_seconds,
            transcript=" ".join(transcript_parts).strip(),
            word_feedback=word_feedback[:160],
            provider_mode="azure",
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

    def _build_word_feedback(self, word_payload: dict) -> WordFeedback:
        pronunciation = word_payload.get("PronunciationAssessment", {})
        score = float(pronunciation.get("AccuracyScore", 0))
        error_type = pronunciation.get("ErrorType", "None")
        phoneme_names = [
            phoneme.get("Phoneme")
            for phoneme in word_payload.get("Phonemes", [])
            if phoneme.get("PronunciationAssessment", {}).get("AccuracyScore", 100) < 75 and phoneme.get("Phoneme")
        ]
        phoneme_hint = ", ".join(phoneme_names[:3]) if phoneme_names else None
        pronunciation_meta = self._word_pronunciation_meta(word_payload.get("Word", ""))
        return WordFeedback(
            word=(word_payload.get("Word", "") or "").strip(),
            score=score,
            status=self._status_from_score(score),
            issue=self._base_issue_from_error(error_type, score, phoneme_hint),
            suggestion=self._base_suggestion_from_error(error_type, word_payload.get("Word", "")),
            start_ms=int(word_payload.get("Offset", 0) / 10000),
            end_ms=int((word_payload.get("Offset", 0) + word_payload.get("Duration", 0)) / 10000),
            error_type=error_type,
            confidence=self._confidence_from_word(score, error_type, phoneme_hint),
            phoneme_hint=phoneme_hint,
            practice_priority=self._priority_from_score(score),
            ipa=pronunciation_meta["ipa"],
            syllables=pronunciation_meta["syllables"],
            stress_syllable=pronunciation_meta["stress_syllable"],
            native_pronunciation=pronunciation_meta["native_pronunciation"],
            slow_pronunciation=pronunciation_meta["slow_pronunciation"],
        )

    async def _compose_response(self, raw: RawAssessment) -> AssessmentResponse:
        top_words = self._prioritize_words(raw.word_feedback)
        metrics = self._metric_insights(raw)
        overview = self._fallback_overview(raw, top_words)
        coach_summary = self._fallback_summary(raw, top_words)
        practice_plan = self._fallback_practice_plan(raw, top_words)
        insights = self._fallback_insights(raw)
        top_issues = self._fallback_top_issues(top_words)

        llm_bundle = await self._generate_llm_bundle(raw, top_words, metrics)
        if llm_bundle:
            overview = self._merge_overview(overview, llm_bundle.get("overview"))
            coach_summary = self._merge_summary(coach_summary, llm_bundle.get("coach_summary"))
            top_issues = self._merge_top_issues(top_issues, llm_bundle.get("top_issues"))
            practice_plan = self._merge_practice_plan(practice_plan, llm_bundle.get("practice_plan"))
            insights = self._merge_insights(insights, llm_bundle.get("insights"))
            self._apply_word_overrides(raw.word_feedback, llm_bundle.get("word_overrides"))

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
        )

    async def _generate_llm_bundle(self, raw: RawAssessment, top_words: list[WordFeedback], metrics: list[MetricInsight]) -> dict | None:
        if not settings.groq_api_key or not top_words:
            return None

        payload = {
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
            "flagged_words": [
                {
                    "word": word.word,
                    "score": word.score,
                    "error_type": word.error_type,
                    "confidence": word.confidence,
                    "phoneme_hint": word.phoneme_hint,
                    "start_ms": word.start_ms,
                    "end_ms": word.end_ms,
                }
                for word in top_words[:8]
            ],
        }
        prompt = (
            "You are an elite English pronunciation coach.\n"
            "Use only the provided structured speech data. Never invent pronunciation mistakes.\n"
            "Return JSON with keys: overview, coach_summary, top_issues, practice_plan, insights, word_overrides.\n"
            "Constraints:\n"
            "- overview.why and coach_summary.summary together should stay concise and practical.\n"
            "- coach_summary.summary must be <= 120 words.\n"
            "- top_issues max 5 items, sorted by coaching priority.\n"
            "- Each word_override must target an existing flagged word by word + start_ms.\n"
            "- Avoid repeated phrases like 'repeat more slowly'. Be specific about stress, endings, consonants, rhythm, or clarity.\n"
            "- If confidence is low, stay conservative and describe only the reliable observation.\n"
            "- practice_plan.sentences must create three natural sentences using difficult words.\n"
            "- Keep copy sounding like a human language coach, not product marketing.\n"
            f"\nStructured input:\n{json.dumps(payload)}"
        )

        try:
            async with httpx.AsyncClient(timeout=45) as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                    json={
                        "model": settings.groq_model,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {"role": "system", "content": "Return strict JSON only."},
                            {"role": "user", "content": prompt},
                        ],
                    },
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                return json.loads(content)
        except Exception:
            return None

    async def _mock_assessment(self, inputs: ProviderInputs) -> RawAssessment:
        transcript = inputs.reference_text.strip() or (
            "I work on AI products, and I want my pronunciation to sound clear, natural, and confident in every conversation."
        )
        words = transcript.replace("\n", " ").split()
        seed = int(hashlib.sha256(f"{transcript}|{inputs.duration_seconds}".encode("utf-8")).hexdigest()[:8], 16)
        word_feedback: list[WordFeedback] = []
        total = 0.0
        for index, word in enumerate(words[:80]):
            base = 61 + ((seed >> (index % 8)) % 36)
            score = float(min(98, max(48, base - (8 if index % 6 == 0 else 0))))
            status_label = self._status_from_score(score)
            total += score
            word_feedback.append(
                WordFeedback(
                    word=word.strip(".,!?"),
                    score=score,
                    status=status_label,
                    issue=self._base_issue_from_error("Mispronunciation" if status_label in {"watch", "needs-practice"} else "None", score, None),
                    suggestion=self._base_suggestion_from_error("Mispronunciation", word),
                    start_ms=index * 520,
                    end_ms=(index + 1) * 520,
                    error_type="Mispronunciation" if status_label in {"watch", "needs-practice"} else "None",
                    confidence="medium",
                    phoneme_hint=None,
                    practice_priority=self._priority_from_score(score),
                )
            )

        overall = round(total / max(len(word_feedback), 1), 1)
        return RawAssessment(
            overall_score=overall,
            accuracy_score=round(min(100, overall + 2.8), 1),
            fluency_score=round(max(55, overall - 2), 1),
            prosody_score=round(max(50, overall - 3.5), 1),
            completeness_score=round(min(100, overall + 4), 1),
            duration_seconds=inputs.duration_seconds,
            transcript=transcript,
            word_feedback=word_feedback,
            provider_mode="mock",
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

    def _prioritize_words(self, words: list[WordFeedback]) -> list[WordFeedback]:
        flagged = [word for word in words if word.status in {"watch", "needs-practice"}]
        if not flagged:
            flagged = sorted(words, key=lambda word: word.score)[:5]
        return sorted(
            flagged,
            key=lambda word: (
                0 if word.practice_priority == "high" else 1 if word.practice_priority == "medium" else 2,
                word.score,
            ),
        )[:5]

    def _metric_insights(self, raw: RawAssessment) -> list[MetricInsight]:
        return [
            MetricInsight(key="overall", label="Overall", score=raw.overall_score, band=self._band(raw.overall_score), explanation=self._overall_explanation(raw)),
            MetricInsight(key="accuracy", label="Accuracy", score=raw.accuracy_score, band=self._band(raw.accuracy_score), explanation="Words were mostly understandable, with deductions concentrated in a small set of low-scoring items."),
            MetricInsight(key="prosody", label="Prosody", score=raw.prosody_score, band=self._band(raw.prosody_score), explanation="This reflects stress, emphasis, and rhythm. Lower prosody usually means speech sounds flatter or the stress lands awkwardly."),
            MetricInsight(key="fluency", label="Fluency", score=raw.fluency_score, band=self._band(raw.fluency_score), explanation="This tracks pacing and smoothness. Hesitations or uneven chunking reduce the feeling of natural flow."),
            MetricInsight(key="completeness", label="Completeness", score=raw.completeness_score, band=self._band(raw.completeness_score), explanation="This shows how much of the expected spoken content Azure could confidently capture."),
        ]

    def _fallback_overview(self, raw: RawAssessment, top_words: list[WordFeedback]) -> CoachOverview:
        word_list = ", ".join(word.word for word in top_words[:4]) or "a few lower-scoring words"
        rounded = round(raw.overall_score)
        headline = f"{rounded}/100"
        return CoachOverview(
            headline=headline,
            level_label=self._level_label(raw.overall_score),
            why=f"Most of the sample was understandable. The main deductions came from {word_list}.",
            cefr_estimate=self._cefr_estimate(raw.overall_score),
            confidence_label=self._confidence_label(raw),
            improvement_potential=self._improvement_potential(raw.overall_score, len(top_words)),
            celebration=self._celebration_line(raw.overall_score, len(top_words)),
        )

    def _fallback_summary(self, raw: RawAssessment, top_words: list[WordFeedback]) -> CoachSummary:
        strong_words = [word.word for word in raw.word_feedback if word.status in {"good", "excellent"}][:3]
        repeated_issue = self._repeated_issue(top_words)
        summary = (
            f"Your pronunciation is strongest when the words are familiar and rhythm is steady. "
            f"Most deductions are coming from {repeated_issue.lower()}. "
            f"Focus on {', '.join(word.word for word in top_words[:3]) or 'the lowest-scoring words'} first instead of repeating the whole recording."
        )
        return CoachSummary(
            summary=summary[:120].rsplit(" ", 1)[0] + "." if len(summary) > 120 else summary,
            strengths=[
                f"Clearer words like {', '.join(strong_words)} stayed stable." if strong_words else "Several words were already easy to understand.",
                "Your recording stayed within a usable fluency range.",
                "The sample had enough content to diagnose priorities.",
            ],
            weaknesses=[
                f"The largest score drops came from {', '.join(word.word for word in top_words[:3])}." if top_words else "A few words caused most deductions.",
                "Sentence rhythm can sound more natural when stress is more consistent.",
                "Some endings or stressed syllables were softer than they should be.",
            ],
            speaking_habits=[
                "You sound more natural on short familiar words.",
                "Technical or multi-syllable words are more likely to lose stress accuracy.",
                "Once a phrase is flowing, your rhythm improves.",
            ],
            repeated_issue=repeated_issue,
            advice="Practice the five hardest words first, then reuse them in short sentences so the improvement transfers into connected speech.",
        )

    def _fallback_top_issues(self, top_words: list[WordFeedback]) -> list[PriorityIssue]:
        issues: list[PriorityIssue] = []
        for word in top_words:
            issues.append(
                PriorityIssue(
                    word=word.word,
                    score=word.score,
                    why=word.issue,
                    likely_issue=self._likely_issue_label(word),
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
        estimated_gain = min(8, max(3, len(top_words) + round((85 - min(raw.overall_score, 85)) / 10)))
        practice_words = [
            PracticeWord(
                word=word.word,
                reason=word.issue,
                drill=self._drill_for_word(word),
                syllable_hint=self._syllable_hint(word.word),
                ipa=word.ipa,
                stress_syllable=word.stress_syllable,
                native_pronunciation=word.native_pronunciation,
                slow_pronunciation=word.slow_pronunciation,
                repetitions=5,
                estimated_gain=2 if word.practice_priority == "high" else 1,
            )
            for word in top_words
        ]
        focus_words = [word.word for word in top_words[:3]]
        practice_sentences = self._practice_sentences(focus_words)
        return PracticePlan(
            today_focus="Fix the hardest words before you re-record the full sample.",
            estimated_score_if_fixed=min(100, round(raw.overall_score) + estimated_gain),
            estimated_gain=estimated_gain,
            words=practice_words,
            sentences=practice_sentences,
        )

    def _fallback_insights(self, raw: RawAssessment) -> list[CoachInsight]:
        scores = [word.score for word in raw.word_feedback]
        words_per_minute = round((len(raw.word_feedback) / max(raw.duration_seconds, 1)) * 60)
        spread = statistics.pstdev(scores) if len(scores) > 1 else 0
        insights = [
            CoachInsight(title="Speaking speed", value=f"{words_per_minute} wpm", description="This estimates how dense the sample felt once pauses are included."),
            CoachInsight(title="Consistency", value="Stable" if spread < 12 else "Mixed", description="Low spread means your word quality stayed more even from start to finish."),
            CoachInsight(title="Word stress", value="Needs attention" if raw.prosody_score < 85 else "Mostly solid", description="Prosody and low-scoring words suggest how often stress landed naturally."),
            CoachInsight(title="Sentence rhythm", value="Natural" if raw.fluency_score >= 88 else "Can improve", description="Rhythm improves when pauses and emphasis sound less mechanical."),
        ]
        if raw.prosody_score >= 70:
            insights.append(
                CoachInsight(
                    title="Confidence",
                    value=self._confidence_label(raw).replace(" confidence", ""),
                    description="This is inferred from steadiness, completeness, and whether only a few words are causing deductions.",
                )
            )
        return insights

    def _merge_overview(self, fallback: CoachOverview, override: dict | None) -> CoachOverview:
        if not override:
            return fallback
        payload = fallback.model_dump()
        payload.update({key: value for key, value in override.items() if value})
        return CoachOverview(**payload)

    def _merge_summary(self, fallback: CoachSummary, override: dict | None) -> CoachSummary:
        if not override:
            return fallback
        payload = fallback.model_dump()
        payload.update({key: value for key, value in override.items() if value})
        return CoachSummary(**payload)

    def _merge_top_issues(self, fallback: list[PriorityIssue], override: list[dict] | None) -> list[PriorityIssue]:
        if not override:
            return fallback
        merged: list[PriorityIssue] = []
        for index, item in enumerate(override[:5]):
            base = fallback[index].model_dump() if index < len(fallback) else fallback[-1].model_dump()
            base.update({key: value for key, value in item.items() if value is not None})
            merged.append(PriorityIssue(**base))
        return merged or fallback

    def _merge_practice_plan(self, fallback: PracticePlan, override: dict | None) -> PracticePlan:
        if not override:
            return fallback
        payload = fallback.model_dump()
        for key, value in override.items():
            if not value:
                continue
            payload[key] = value
        return PracticePlan(**payload)

    def _merge_insights(self, fallback: list[CoachInsight], override: list[dict] | None) -> list[CoachInsight]:
        if not override:
            return fallback
        try:
            return [CoachInsight(**item) for item in override]
        except Exception:
            return fallback

    def _apply_word_overrides(self, words: list[WordFeedback], overrides: list[dict] | None) -> None:
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

    def _confidence_from_word(self, score: float, error_type: str, phoneme_hint: str | None) -> str:
        if phoneme_hint or error_type not in {"None", ""}:
            return "high" if score < 82 else "medium"
        if score < 65:
            return "low"
        return "medium"

    def _base_issue_from_error(self, error_type: str, score: float, phoneme_hint: str | None) -> str:
        if score < 55 and not phoneme_hint and error_type in {"None", ""}:
            return "This word stood out as less clear than the rest of the sample, so it should be one of your first practice targets."
        if error_type == "Omission":
            return "Part of this word sounded incomplete, so the ending or an internal consonant may have dropped out."
        if error_type == "Insertion":
            return "An extra sound likely slipped into this word, which made it sound less natural."
        if phoneme_hint:
            return f"The lowest-confidence sounds were around {phoneme_hint}, which usually points to articulation or stress slipping on this word."
        if score < 72:
            return "This word sounded less clear than the rest of the sample and likely lost stress or consonant sharpness."
        if score < 84:
            return "This word was understandable, but it still sounded less natural than your strongest words."
        return "This word was pronounced clearly."

    def _base_suggestion_from_error(self, error_type: str, word: str) -> str:
        clean_word = (word or "this word").strip()
        if error_type == "Omission":
            return f"Slow down on {clean_word} and make the ending fully audible before you speed it back up."
        if error_type == "Insertion":
            return f"Say {clean_word} once syllable by syllable, then repeat it without adding extra vowel sounds."
        return f"Practice {clean_word} in short bursts and exaggerate the stressed syllable before returning to natural speed."

    def _band(self, score: float) -> str:
        if score >= 90:
            return "Excellent"
        if score >= 82:
            return "Strong"
        if score >= 72:
            return "Developing"
        return "Needs work"

    def _overall_explanation(self, raw: RawAssessment) -> str:
        weak_count = len([word for word in raw.word_feedback if word.status in {"watch", "needs-practice"}])
        return f"Only {weak_count} words are creating most of the score drop, so targeted practice should move the overall result faster than repeating the whole sample."

    def _level_label(self, score: float) -> str:
        if score >= 92:
            return "Excellent pronunciation"
        if score >= 84:
            return "Strong pronunciation"
        if score >= 74:
            return "Good foundation"
        return "Needs focused practice"

    def _cefr_estimate(self, score: float) -> str:
        if score >= 92:
            return "C1 speaking quality"
        if score >= 84:
            return "B2-C1 speaking quality"
        if score >= 74:
            return "B2 speaking quality"
        return "B1-B2 speaking quality"

    def _confidence_label(self, raw: RawAssessment) -> str:
        low_confidence = len([word for word in raw.word_feedback if word.confidence == "low"])
        if raw.completeness_score >= 90 and low_confidence <= 1:
            return "High confidence"
        if raw.completeness_score >= 78:
            return "Medium confidence"
        return "Limited confidence"

    def _improvement_potential(self, overall_score: float, top_word_count: int) -> str:
        if overall_score >= 90 and top_word_count <= 3:
            return "Small changes could push you into the mid-90s"
        if overall_score >= 80:
            return "A short focused drill session should produce visible gains"
        return "There is plenty of room to improve quickly with targeted word practice"

    def _celebration_line(self, overall_score: float, top_word_count: int) -> str:
        if overall_score >= 90:
            return f"Excellent. Only {top_word_count} words are keeping you from an elite result."
        if overall_score >= 80:
            return "You already sound understandable. The next jump comes from cleaning up a small set of problem words."
        return "You have a useful base already. Focused coaching on the hardest words will lift the whole recording."

    def _repeated_issue(self, top_words: list[WordFeedback]) -> str:
        if not top_words:
            return "general clarity"
        omission_count = len([word for word in top_words if word.error_type == "Omission"])
        insertion_count = len([word for word in top_words if word.error_type == "Insertion"])
        low_confidence_count = len([word for word in top_words if word.confidence == "low"])
        if omission_count >= max(insertion_count, 2):
            return "Dropped sounds at word endings"
        if insertion_count >= 2:
            return "Extra vowel sounds inside words"
        if low_confidence_count >= 2:
            return "Unclear articulation on the weakest words"
        return "Word stress and articulation"

    def _likely_issue_label(self, word: WordFeedback) -> str:
        if word.confidence == "low":
            return "Low-confidence word"
        if word.error_type == "Omission":
            return "Missing sound or softened ending"
        if word.error_type == "Insertion":
            return "Extra sound added"
        if word.phoneme_hint:
            return f"Articulation slipped around {word.phoneme_hint}"
        return "Stress or clarity issue"

    def _drill_for_word(self, word: WordFeedback) -> str:
        return (
            f"Say {word.word} five times. Start slowly, exaggerate the stressed part, then say it once at natural speed."
            if word.confidence != "low"
            else f"Repeat {word.word} in isolation first, then place it inside a short sentence once it sounds clearer."
        )

    def _syllable_hint(self, word: str) -> str:
        clean = "".join(char for char in word if char.isalpha())
        if len(clean) <= 4:
            return clean
        midpoint = max(2, len(clean) // 2)
        return f"{clean[:midpoint]}-{clean[midpoint:]}"

    def _word_pronunciation_meta(self, word: str) -> dict[str, object]:
        clean = "".join(char for char in word.lower() if char.isalpha())
        fallback = {
            "ipa": None,
            "syllables": self._heuristic_syllables(clean),
            "stress_syllable": None,
            "native_pronunciation": word,
            "slow_pronunciation": " - ".join(self._heuristic_syllables(clean)) if clean else word,
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
        syllables = pronouncing.syllable_count(selected)
        stresses = pronouncing.stresses(selected)
        stress_syllable = next((index + 1 for index, digit in enumerate(stresses) if digit == "1"), None)
        split = self._syllabify_arpabet(selected.split())
        ipa = self._arpabet_to_ipa(selected)
        return {
            "ipa": ipa,
            "syllables": split or fallback["syllables"],
            "stress_syllable": stress_syllable if stress_syllable and stress_syllable <= max(len(split), syllables or 1) else None,
            "native_pronunciation": word,
            "slow_pronunciation": " - ".join(split) if split else fallback["slow_pronunciation"],
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

    def _practice_sentences(self, words: list[str]) -> list[PracticeSentence]:
        unique_words = [word for word in words if word]
        defaults = ["communication", "clarity", "confidence"]
        while len(unique_words) < 3:
            unique_words.append(defaults[len(unique_words)])
        return [
            PracticeSentence(
                sentence=f"I want my {unique_words[0]} to sound clearer in professional conversations.",
                focus_words=[unique_words[0]],
            ),
            PracticeSentence(
                sentence=f"Steady practice helps me pronounce {unique_words[1]} with more confidence.",
                focus_words=[unique_words[1]],
            ),
            PracticeSentence(
                sentence=f"I can use {unique_words[2]} naturally when I slow down and control the stress.",
                focus_words=[unique_words[2]],
            ),
        ]
