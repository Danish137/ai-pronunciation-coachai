import React from "react";
import type { PracticePlan } from "../types/assessment";

type PracticePanelProps = {
  practicePlan: PracticePlan;
};

function speak(text: string, rate: number) {
  if (!("speechSynthesis" in window)) return;
  const u = new SpeechSynthesisUtterance(text);
  u.rate = rate;
  u.lang = "en-US";
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(u);
}

export function PracticePanel({ practicePlan }: PracticePanelProps) {
  if (!practicePlan.sentences.length) return null;

  return (
    <section className="practice-card">
      <div className="section-header">
        <div>
          <span className="small-label">Practice sentences</span>
          <h3>Use your words in natural context</h3>
          <p>Ordered from simpler to more complex so you build real fluency, not just repetition.</p>
        </div>
      </div>

      <ol className="sentence-list">
        {practicePlan.sentences.map((sentence) => (
          <li key={sentence.sentence} className="sentence-item">
            <div className="sentence-body">
              <p className="sentence-text">
                {sentence.focus_words.length
                  ? highlightFocusWords(sentence.sentence, sentence.focus_words)
                  : sentence.sentence}
              </p>
              <div className="sentence-actions">
                <button className="ghost-button" type="button" onClick={() => speak(sentence.sentence, 0.92)}>Hear it</button>
                <button className="ghost-button" type="button" onClick={() => speak(sentence.sentence, 0.6)}>Slow</button>
              </div>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

function highlightFocusWords(sentence: string, focusWords: string[]): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  let remaining = sentence;
  let key = 0;
  for (const fw of focusWords) {
    const idx = remaining.toLowerCase().indexOf(fw.toLowerCase());
    if (idx === -1) continue;
    if (idx > 0) parts.push(<span key={key++}>{remaining.slice(0, idx)}</span>);
    parts.push(<mark key={key++} className="focus-word">{remaining.slice(idx, idx + fw.length)}</mark>);
    remaining = remaining.slice(idx + fw.length);
  }
  if (remaining) parts.push(<span key={key++}>{remaining}</span>);
  return parts.length ? parts : [<span key={0}>{sentence}</span>];
}

