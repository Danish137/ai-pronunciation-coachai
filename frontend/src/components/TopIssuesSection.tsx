import { useState } from "react";

import type { PracticeWord, PriorityIssue, PracticePlan } from "../types/assessment";

type TopIssuesSectionProps = {
  issues: PriorityIssue[];
  practicePlan: PracticePlan;
  onSelectWord: (startMs: number) => void;
};

function speak(text: string, rate: number) {
  if (!("speechSynthesis" in window)) return;
  const u = new SpeechSynthesisUtterance(text);
  u.rate = rate;
  u.lang = "en-US";
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(u);
}

function IssueCard({
  issue,
  practiceWord,
  rank,
  onSelectWord,
}: {
  issue: PriorityIssue;
  practiceWord: PracticeWord | undefined;
  rank: number;
  onSelectWord: (startMs: number) => void;
}) {
  const [expanded, setExpanded] = useState(rank === 1);
  const [reps, setReps] = useState(0);
  const targetReps = practiceWord?.repetitions ?? 5;

  return (
    <article className={`issue-card priority-${issue.priority}`}>
      <button
        className="issue-card-header"
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        <div className="issue-card-title">
          <span className="issue-rank">{rank}</span>
          <div>
            <strong className="issue-word">{issue.word}</strong>
            {issue.ipa ? <span className="issue-ipa">{issue.ipa}</span> : null}
          </div>
        </div>
        <div className="issue-card-right">
          <span className={`issue-score score-${issue.difficulty}`}>{Math.round(issue.score)}</span>
          <span className="issue-chevron">{expanded ? "▲" : "▼"}</span>
        </div>
      </button>

      {expanded ? (
        <div className="issue-body">
          <p className="issue-problem">{issue.why}</p>
          {issue.practice_tip ? <p className="issue-tip">{issue.practice_tip}</p> : null}

          {issue.syllables.length > 0 ? (
            <div className="issue-syllables">
              {issue.syllables.map((syl, i) => (
                <span key={i} className={`syl-chip ${issue.stress_syllable === i + 1 ? "stressed" : ""}`}>
                  {syl}
                </span>
              ))}
            </div>
          ) : null}

          {practiceWord?.drill ? (
            <div className="issue-drill">
              <span className="small-label">Practice</span>
              <p>{practiceWord.drill}</p>
            </div>
          ) : issue.drill ? (
            <div className="issue-drill">
              <span className="small-label">Practice</span>
              <p>{issue.drill}</p>
            </div>
          ) : null}

          <div className="issue-actions">
            <button
              className="ghost-button"
              type="button"
              onClick={() => speak(issue.native_pronunciation ?? issue.word, 0.92)}
            >
              Hear native
            </button>
            <button
              className="ghost-button"
              type="button"
              onClick={() => speak(issue.slow_pronunciation ?? issue.word, 0.55)}
            >
              Hear slow
            </button>
            <button
              className="ghost-button"
              type="button"
              onClick={() => onSelectWord(issue.start_ms)}
            >
              In transcript
            </button>
          </div>

          <div className="rep-section">
            <div className="rep-track" aria-label={`${reps} of ${targetReps} repetitions`}>
              {Array.from({ length: targetReps }).map((_, i) => (
                <span key={i} className={`rep-dot ${i < reps ? "filled" : ""}`} />
              ))}
            </div>
            <button
              className="secondary-button rep-button"
              type="button"
              onClick={() => setReps((v) => Math.min(targetReps, v + 1))}
              disabled={reps >= targetReps}
            >
              {reps >= targetReps ? "Done ✓" : "I said it"}
            </button>
          </div>
        </div>
      ) : null}
    </article>
  );
}

export function TopIssuesSection({ issues, practicePlan, onSelectWord }: TopIssuesSectionProps) {
  const practiceWordMap = new Map(practicePlan.words.map((w) => [w.word.toLowerCase(), w]));

  return (
    <section className="issues-card">
      <div className="section-header">
        <div>
          <span className="small-label">Top priorities</span>
          <h3>Fix these first</h3>
          <p>Each card shows the problem, a practice tip, and repetition tracking.</p>
        </div>
      </div>
      <div className="issue-list">
        {issues.map((issue, index) => (
          <IssueCard
            key={`${issue.word}-${issue.start_ms}`}
            issue={issue}
            practiceWord={practiceWordMap.get(issue.word.toLowerCase())}
            rank={index + 1}
            onSelectWord={onSelectWord}
          />
        ))}
      </div>
    </section>
  );
}

