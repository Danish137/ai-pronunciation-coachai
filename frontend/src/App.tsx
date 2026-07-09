import { startTransition, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import axios from "axios";

import { CoachSummaryPanel } from "./components/CoachSummaryPanel";
import { HistoryPanel } from "./components/HistoryPanel";
import { PracticePanel } from "./components/PracticePanel";
import { ProgressPipeline } from "./components/ProgressPipeline";
import { ResultHeader } from "./components/ResultHeader";
import { TopIssuesSection } from "./components/TopIssuesSection";
import { TranscriptViewer } from "./components/TranscriptViewer";
import { UploadCard } from "./components/UploadCard";
import { useAssessmentHistory, useDeleteAttempt, useDeleteHistory } from "./hooks/useAssessmentHistory";
import { useProcessingPipeline } from "./hooks/useProcessingPipeline";
import { createAssessment } from "./lib/api";
import { validateAudioDuration } from "./lib/audio";
import type { Assessment, SourceType, WordFeedback } from "./types/assessment";

const ACCEPTED_AUDIO_TYPES = ".wav,.mp3,.m4a,.webm,audio/wav,audio/mpeg,audio/mp4,audio/webm";

function App() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedDuration, setSelectedDuration] = useState<number | null>(null);
  const [sourceType, setSourceType] = useState<SourceType>("upload");
  const [consentAccepted, setConsentAccepted] = useState(false);
  const [error, setError] = useState("");
  const [activeAttempt, setActiveAttempt] = useState<Assessment | null>(null);
  const [selectedWordStartMs, setSelectedWordStartMs] = useState<number | null>(null);

  const historyQuery = useAssessmentHistory();
  const deleteAttemptMutation = useDeleteAttempt();
  const deleteHistoryMutation = useDeleteHistory();

  const assessmentMutation = useMutation({
    mutationFn: createAssessment,
    onSuccess: (attempt) => {
      console.debug("Assessment mutation success", attempt);
      startTransition(() => {
        setActiveAttempt(attempt);
        setSelectedWordStartMs(attempt.top_issues[0]?.start_ms ?? attempt.word_feedback[0]?.start_ms ?? null);
      });
      setError("");
      historyQuery.refetch();
    },
    onError: (mutationError: unknown) => {
      const message = axios.isAxiosError(mutationError)
        ? mutationError.response?.data?.detail || mutationError.message
        : mutationError instanceof Error
          ? mutationError.message
          : "We could not process this recording. Check your network and try again.";
      setError(message);
    },
  });

  const pipeline = useProcessingPipeline(assessmentMutation.isPending);
  const currentAttempt = activeAttempt ?? historyQuery.data?.[0] ?? null;
  console.debug("Current attempt for render", currentAttempt);

  const selectedFileLabel = useMemo(() => {
    if (!selectedFile || selectedDuration === null) {
      return null;
    }
    return `${selectedFile.name} • ${sourceType} • ${selectedDuration.toFixed(1)}s`;
  }, [selectedDuration, selectedFile, sourceType]);

  const canSubmit = Boolean(selectedFile && selectedDuration !== null && consentAccepted && !assessmentMutation.isPending);

  const improvementDelta = useMemo(() => {
    if (!currentAttempt || !historyQuery.data?.length) {
      return null;
    }
    const currentIndex = historyQuery.data.findIndex((attempt) => attempt.id === currentAttempt.id);
    const previousAttempt = currentIndex >= 0 ? historyQuery.data[currentIndex + 1] : historyQuery.data[1];
    if (!previousAttempt) {
      return null;
    }
    return Math.round(currentAttempt.overall_score - previousAttempt.overall_score);
  }, [currentAttempt, historyQuery.data]);

  async function handleFileChange(file: File | null, nextSourceType: SourceType, knownDuration?: number) {
    setError("");
    setSourceType(nextSourceType);
    setSelectedFile(file);
    setSelectedDuration(null);

    if (!file) {
      return;
    }

    // Recordings already validated inside Recorder.tsx — trust the elapsed seconds directly
    // because webm blobs from MediaRecorder have Infinity duration metadata.
    if (knownDuration !== undefined) {
      setSelectedDuration(knownDuration);
      return;
    }

    try {
      const duration = await validateAudioDuration(file);
      setSelectedDuration(duration);
    } catch (validationError) {
      setSelectedFile(null);
      setError(validationError instanceof Error ? validationError.message : "Invalid audio.");
    }
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedFile || selectedDuration === null) {
      setError("Choose or record a valid 30 to 45 second audio sample first.");
      return;
    }
    if (!consentAccepted) {
      setError("Please accept consent before analyzing audio.");
      return;
    }

    await assessmentMutation.mutateAsync({
      file: selectedFile,
      sourceType,
      consentAccepted,
      referenceText: "",
    });
  }

  function handleSelectWord(word: WordFeedback) {
    startTransition(() => {
      setSelectedWordStartMs(word.start_ms);
    });
  }

  return (
    <div className="app-shell">
      <main className="coach-layout">
        <UploadCard
          acceptedTypes={ACCEPTED_AUDIO_TYPES}
          consentAccepted={consentAccepted}
          error={error}
          isSubmitting={assessmentMutation.isPending}
          onConsentChange={setConsentAccepted}
          onFileChange={(file, type, knownDuration) => {
            void handleFileChange(file, type, knownDuration);
          }}
          onSubmit={handleSubmit}
          selectedFileLabel={selectedFileLabel}
          canSubmit={canSubmit}
        />

        <ProgressPipeline steps={pipeline.steps} stepIndex={pipeline.stepIndex} progressPct={pipeline.progressPct} visible={assessmentMutation.isPending} />

        {currentAttempt ? (
          <div className="results-stack">
            <ResultHeader assessment={currentAttempt} improvementDelta={improvementDelta} />
            <TopIssuesSection
              issues={currentAttempt.top_issues}
              practicePlan={currentAttempt.practice_plan}
              onSelectWord={(startMs) => setSelectedWordStartMs(startMs)}
            />
            <TranscriptViewer words={currentAttempt.word_feedback} selectedStartMs={selectedWordStartMs} onSelectWord={handleSelectWord} />
            <CoachSummaryPanel summary={currentAttempt.coach_summary} />
            <PracticePanel practicePlan={currentAttempt.practice_plan} />
            <HistoryPanel
              attempts={historyQuery.data ?? []}
              activeAttemptId={currentAttempt.id}
              onSelect={(attempt) => {
                startTransition(() => {
                  setActiveAttempt(attempt);
                  setSelectedWordStartMs(attempt.top_issues[0]?.start_ms ?? attempt.word_feedback[0]?.start_ms ?? null);
                });
              }}
              onDelete={(id) => deleteAttemptMutation.mutate(id)}
              onDeleteAll={() => deleteHistoryMutation.mutate()}
              deletingAll={deleteHistoryMutation.isPending}
            />
          </div>
        ) : (
          <section className="empty-result-card">
            <div className="empty-illustration" aria-hidden="true" />
            <h2>Record your first pronunciation sample</h2>
            <p>We will show your score, the five most important words to fix, a highlighted transcript, and a short practice plan.</p>
          </section>
        )}
      </main>
    </div>
  );
}

export default App;
