import type { Assessment } from "../types/assessment";

type ResultHeaderProps = {
  assessment: Assessment;
  improvementDelta: number | null;
};

export function ResultHeader({ assessment, improvementDelta }: ResultHeaderProps) {
  const dur = Math.round(assessment.duration_seconds);
  const providerLabel = assessment.provider_mode === "azure" ? "Live analysis" : "Mock mode";

  return (
    <section className="result-header">
      <div className="result-main">
        <div className="score-block">
          <span className="score-big">{Math.round(assessment.overall_score)}</span>
          <span className="score-denom">/100</span>
        </div>
        <div className="result-text">
          <h2>{assessment.overview.level_label}</h2>
          <p>{assessment.overview.why}</p>
        </div>
      </div>

      <div className="result-pills">
        <span className="result-pill">{assessment.overview.confidence_label}</span>
        <span className="result-pill">{dur}s recording</span>
        <span className="result-pill">{providerLabel}</span>
        {improvementDelta !== null ? (
          <span className={`result-pill ${improvementDelta >= 0 ? "pill-positive" : "pill-negative"}`}>
            {improvementDelta >= 0 ? `+${improvementDelta}` : improvementDelta} from last attempt
          </span>
        ) : null}
      </div>

      <div className="result-highlight">
        <p className="celebration-note">{assessment.overview.celebration}</p>
        {assessment.overview.improvement_potential ? (
          <p className="result-subcopy">{assessment.overview.improvement_potential}</p>
        ) : null}
      </div>
    </section>
  );
}
