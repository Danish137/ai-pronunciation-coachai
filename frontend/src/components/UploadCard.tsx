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
  selectedFileLabel: string | null;
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
  selectedFileLabel,
  canSubmit,
}: UploadCardProps) {
  return (
    <section className="intake-card">
      <div className="intro-copy">
        <h1>Improve your English pronunciation</h1>
        <p>Upload or record a 30 to 45 second sample and receive personalized coaching.</p>
      </div>

      <div className="intake-rules" aria-label="Recording rules">
        <span>30-45 seconds</span>
        <span>English only</span>
        <span>WAV, MP3, M4A, WEBM</span>
      </div>

      <form onSubmit={onSubmit} className="assessment-form">
        <div className="capture-layout">
          <label className="upload-dropzone">
            <input
              type="file"
              accept={acceptedTypes}
              onChange={(event) => {
                const file = event.target.files?.[0] ?? null;
                onFileChange(file, "upload");
              }}
            />
            <span className="small-label">Upload audio</span>
            <strong>Select a recording</strong>
            <p>Choose a natural English sample. You do not need a script.</p>
          </label>

          <Recorder
            onReady={(file) => {
              onFileChange(file, "recording");
            }}
          />
        </div>

        <label className="consent-row">
          <input type="checkbox" checked={consentAccepted} onChange={(event) => onConsentChange(event.target.checked)} />
          <span>I consent to audio processing for pronunciation coaching. Raw audio is removed after analysis.</span>
        </label>

        <div className="submit-row">
          <div className="selected-file-copy">
            <strong>{selectedFileLabel ?? "Choose or record a valid sample to begin."}</strong>
            <p>Analysis unlocks once the sample is in range and consent is checked.</p>
          </div>
          <button className="primary-button" disabled={!canSubmit || isSubmitting}>
            {isSubmitting ? "Analyzing..." : "Analyze pronunciation"}
          </button>
        </div>

        {error ? <p className="error-text">{error}</p> : null}
      </form>
    </section>
  );
}
