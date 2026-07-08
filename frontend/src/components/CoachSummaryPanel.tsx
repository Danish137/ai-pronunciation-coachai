import type { CoachSummary } from "../types/assessment";

type CoachSummaryPanelProps = {
  summary: CoachSummary;
};

export function CoachSummaryPanel({ summary }: CoachSummaryPanelProps) {
  return (
    <section className="coach-summary-card">
      <div className="section-copy">
        <span className="section-kicker">AI summary</span>
        <h3>Your coach's read on this recording</h3>
        <p>{summary.summary}</p>
      </div>

      <div className="summary-grid">
        <div className="summary-block">
          <strong>Strengths</strong>
          <ul>
            {summary.strengths.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
        <div className="summary-block">
          <strong>Weaknesses</strong>
          <ul>
            {summary.weaknesses.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
        <div className="summary-block">
          <strong>Speaking habits</strong>
          <ul>
            {summary.speaking_habits.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      </div>

      <div className="advice-strip">
        <div>
          <span className="section-kicker">Most repeated issue</span>
          <strong>{summary.repeated_issue}</strong>
        </div>
        <p>{summary.advice}</p>
      </div>
    </section>
  );
}
