import type { CoachSummary } from "../types/assessment";

type CoachSummaryPanelProps = {
  summary: CoachSummary;
};

export function CoachSummaryPanel({ summary }: CoachSummaryPanelProps) {
  return (
    <section className="coach-summary-card">
      <div className="summary-heading">
        <span className="small-label">Coach's note</span>
        <h3>What this recording says about your speech</h3>
        <p>{summary.summary}</p>
      </div>

      <div className="summary-columns">
        <div>
          <strong>Strongest areas</strong>
          <ul>
            {summary.strengths.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
        <div>
          <strong>Main weaknesses</strong>
          <ul>
            {summary.weaknesses.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      </div>

      <div className="summary-note">
        <div>
          <span className="small-label">Repeated pattern</span>
          <strong>{summary.repeated_issue}</strong>
        </div>
        <p>{summary.advice}</p>
      </div>
    </section>
  );
}
