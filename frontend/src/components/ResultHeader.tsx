import type { Assessment } from "../types/assessment";

type ResultHeaderProps = {
  assessment: Assessment;
  improvementDelta: number | null;
};

export function ResultHeader({ assessment, improvementDelta }: ResultHeaderProps) {
  return (
    <section className="result-header">
      <div className="result-main">
        <div className="score-line">
          <strong>{Math.round(assessment.overall_score)}</strong>
          <span>/100</span>
        </div>
        <div>
          <h2>{assessment.overview.level_label}</h2>
          <p>{assessment.overview.why}</p>
        </div>
      </div>

      <div className="result-meta">
        <span>{assessment.overview.confidence_label}</span>
        <span>{assessment.overview.cefr_estimate}</span>
        <span>{Math.round(assessment.duration_seconds)}s</span>
        {improvementDelta !== null ? <span className={improvementDelta >= 0 ? "positive-text" : "negative-text"}>{improvementDelta >= 0 ? `+${improvementDelta}` : improvementDelta} from last attempt</span> : null}
      </div>

      <p className="celebration-note">{assessment.overview.celebration}</p>
    </section>
  );
}
