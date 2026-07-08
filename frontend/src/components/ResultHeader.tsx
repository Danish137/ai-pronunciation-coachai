import type { Assessment } from "../types/assessment";

type ResultHeaderProps = {
  assessment: Assessment;
  improvementDelta: number | null;
};

export function ResultHeader({ assessment, improvementDelta }: ResultHeaderProps) {
  return (
    <section className="result-hero">
      <div className="result-score">
        <span className="section-kicker">Overall result</span>
        <div className="score-line">
          <strong>{Math.round(assessment.overall_score)}</strong>
          <span>/100</span>
        </div>
        <h2>{assessment.overview.level_label}</h2>
        <p>{assessment.overview.why}</p>
      </div>

      <div className="result-meta">
        <div className="meta-pill">
          <span>CEFR</span>
          <strong>{assessment.overview.cefr_estimate}</strong>
        </div>
        <div className="meta-pill">
          <span>Confidence</span>
          <strong>{assessment.overview.confidence_label}</strong>
        </div>
        <div className="meta-pill">
          <span>Potential</span>
          <strong>{assessment.overview.improvement_potential}</strong>
        </div>
        <div className="meta-pill">
          <span>Duration</span>
          <strong>{Math.round(assessment.duration_seconds)}s</strong>
        </div>
        {improvementDelta !== null ? (
          <div className={`meta-pill ${improvementDelta >= 0 ? "positive" : "negative"}`}>
            <span>Since last attempt</span>
            <strong>{improvementDelta >= 0 ? `+${improvementDelta}` : improvementDelta}</strong>
          </div>
        ) : null}
      </div>

      <p className="celebration-note">{assessment.overview.celebration}</p>
    </section>
  );
}
