import type { PriorityIssue } from "../types/assessment";

type TopIssuesSectionProps = {
  issues: PriorityIssue[];
  onSelectWord: (startMs: number) => void;
};

export function TopIssuesSection({ issues, onSelectWord }: TopIssuesSectionProps) {
  return (
    <section className="issues-card">
      <div className="section-header">
        <div>
          <span className="small-label">Top words to practice</span>
          <h3>Fix these first</h3>
        </div>
      </div>
      <div className="issue-list">
        {issues.map((issue, index) => (
          <article key={`${issue.word}-${issue.start_ms}`} className={`issue-card priority-${issue.priority}`}>
            <div className="issue-top">
              <div>
                <span className="issue-rank">{index + 1}</span>
                <strong>{issue.word}</strong>
              </div>
              <span className="issue-score">{Math.round(issue.score)}</span>
            </div>
            <p className="issue-problem">{issue.why}</p>
            <p className="issue-practice">{issue.practice_tip}</p>
            <div className="issue-details">
              {issue.ipa ? <span>{issue.ipa}</span> : null}
              {issue.syllables.length ? <span>{issue.syllables.join(" • ")}</span> : null}
              {issue.stress_syllable ? <span>Stress {issue.stress_syllable}</span> : null}
            </div>
            <button className="inline-button" type="button" onClick={() => onSelectWord(issue.start_ms)}>
              Open in transcript
            </button>
          </article>
        ))}
      </div>
    </section>
  );
}
