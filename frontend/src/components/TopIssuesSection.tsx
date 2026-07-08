import type { PriorityIssue } from "../types/assessment";

type TopIssuesSectionProps = {
  issues: PriorityIssue[];
  onSelectWord: (startMs: number) => void;
};

export function TopIssuesSection({ issues, onSelectWord }: TopIssuesSectionProps) {
  return (
    <section className="issues-card">
      <div className="section-copy">
        <span className="section-kicker">Biggest problems</span>
        <h3>Practice these first</h3>
        <p>The coach is prioritizing the small number of words that are causing most of the score drop.</p>
      </div>
      <div className="issue-list">
        {issues.map((issue, index) => (
          <article key={`${issue.word}-${issue.start_ms}`} className={`issue-card priority-${issue.priority}`}>
            <div className="issue-header">
              <span>{index + 1}</span>
              <div>
                <strong>{issue.word}</strong>
                <p>{Math.round(issue.score)}/100</p>
              </div>
              <button className="inline-button" type="button" onClick={() => onSelectWord(issue.start_ms)}>
                View in transcript
              </button>
            </div>
            <p className="issue-label">{issue.likely_issue}</p>
            <p>{issue.why}</p>
            <div className="issue-meta">
              <span>{issue.priority} priority</span>
              <span>{issue.difficulty} difficulty</span>
              <span>{issue.confidence} confidence</span>
            </div>
            <p><strong>Practice:</strong> {issue.practice_tip}</p>
            <p><strong>Drill:</strong> {issue.drill}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
