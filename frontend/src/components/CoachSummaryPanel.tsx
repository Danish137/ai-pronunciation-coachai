import type { CoachSummary } from "../types/assessment";

type CoachSummaryPanelProps = {
  summary: CoachSummary;
};

export function CoachSummaryPanel({ summary }: CoachSummaryPanelProps) {
  // Build a coherent paragraph from the available fields
  const parts: string[] = [];
  if (summary.summary) parts.push(summary.summary);
  if (summary.advice && summary.advice !== summary.summary) parts.push(summary.advice);

  const paragraph = parts.join(" ");

  return (
    <section className="coach-summary-card">
      <div className="summary-heading">
        <span className="small-label">AI Coach</span>
        <h3>What your coach noticed</h3>
      </div>

      {paragraph ? <p className="coach-paragraph">{paragraph}</p> : null}

      {summary.repeated_issue ? (
        <div className="coach-pattern">
          <span className="small-label">Repeated pattern</span>
          <p>{summary.repeated_issue}</p>
        </div>
      ) : null}

      {summary.strengths.length > 0 || summary.weaknesses.length > 0 ? (
        <div className="summary-columns">
          {summary.strengths.length > 0 ? (
            <div>
              <strong>Strengths</strong>
              <ul>{summary.strengths.map((s) => <li key={s}>{s}</li>)}</ul>
            </div>
          ) : null}
          {summary.weaknesses.length > 0 ? (
            <div>
              <strong>To improve</strong>
              <ul>{summary.weaknesses.map((s) => <li key={s}>{s}</li>)}</ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

