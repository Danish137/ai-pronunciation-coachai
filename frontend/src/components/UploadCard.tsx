import { useState } from "react";

import type { SourceType } from "../types/assessment";
import { Recorder } from "./Recorder";

type UploadCardProps = {
  acceptedTypes: string;
  consentAccepted: boolean;
  error: string;
  isSubmitting: boolean;
  onConsentChange: (value: boolean) => void;
  onFileChange: (file: File | null, sourceType: SourceType) => void;
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
  referenceText: string;
  selectedFileLabel: string | null;
  onReferenceTextChange: (value: string) => void;
  canSubmit: boolean;
};

export function UploadCard({
  acceptedTypes,
  consentAccepted,
  error,
  isSubmitting,
  onConsentChange,
  onFileChange,
  onSubmit,
  referenceText,
  selectedFileLabel,
  onReferenceTextChange,
  canSubmit,
}: UploadCardProps) {
  const [advancedOpen, setAdvancedOpen] = useState(false);

  return (
    <section className="intake-card">
      <div className="section-copy">
        <span className="section-kicker">Start a new check</span>
        <h2>Upload or record 30 to 45 seconds of English speech.</h2>
        <p>
          The coach works best when the sample is natural, uninterrupted, and long enough to reveal your speaking habits. Most
          users can leave advanced settings alone.
        </p>
      </div>

      <div className="intake-rules" aria-label="Recording rules">
        <span>30-45 seconds</span>
        <span>English only</span>
        <span>Upload or record</span>
      </div>

      <form onSubmit={onSubmit} className="assessment-form">
        <div className="upload-grid">
          <label className="upload-dropzone">
            <input
              type="file"
              accept={acceptedTypes}
              onChange={(event) => {
                const file = event.target.files?.[0] ?? null;
                onFileChange(file, "upload");
              }}
            />
            <div>
              <span className="section-kicker">Upload audio</span>
              <strong>Select an existing recording</strong>
              <p>Supported: WAV, MP3, M4A, WEBM</p>
            </div>
          </label>

          <Recorder
            onReady={(file) => {
              onFileChange(file, "recording");
            }}
          />
        </div>

        <details className="advanced-panel" open={advancedOpen} onToggle={(event) => setAdvancedOpen(event.currentTarget.open)}>
          <summary>Advanced (Optional)</summary>
          <label className="field">
            <span>Reference passage</span>
            <textarea
              rows={4}
              value={referenceText}
              onChange={(event) => onReferenceTextChange(event.target.value)}
              placeholder="Leave blank for free speech. Add a script only when you want exact read-aloud assessment."
            />
          </label>
        </details>

        <label className="consent-row">
          <input type="checkbox" checked={consentAccepted} onChange={(event) => onConsentChange(event.target.checked)} />
          <span>I consent to audio processing for pronunciation coaching. Raw audio is temporary and not kept as part of history.</span>
        </label>

        <div className="submit-row">
          <div>
            <strong>{selectedFileLabel ?? "No valid audio selected yet"}</strong>
            <p className="subtle-copy">Analysis stays disabled until the recording length is valid and consent is accepted.</p>
          </div>
          <button className="primary-button" disabled={!canSubmit || isSubmitting}>
            {isSubmitting ? "Coaching in progress..." : "Analyze pronunciation"}
          </button>
        </div>

        {error ? <p className="error-text">{error}</p> : null}
      </form>
    </section>
  );
}
