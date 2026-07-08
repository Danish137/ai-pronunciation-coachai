import { useState } from "react";

import type { PracticePlan } from "../types/assessment";

type PracticePanelProps = {
  practicePlan: PracticePlan;
};

export function PracticePanel({ practicePlan }: PracticePanelProps) {
  const [repetitionCounts, setRepetitionCounts] = useState<Record<string, number>>({});

  function speak(text: string, rate: number) {
    if (!("speechSynthesis" in window)) {
      return;
    }
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = rate;
    utterance.lang = "en-US";
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
  }

  return (
    <section className="practice-card">
      <div className="section-header">
        <div>
          <span className="small-label">Practice session</span>
          <h3>{practicePlan.today_focus}</h3>
          <p>Improving these words should noticeably raise your overall pronunciation quality.</p>
        </div>
      </div>

      <div className="practice-word-list">
        {practicePlan.words.map((word) => {
          const count = repetitionCounts[word.word] ?? 0;
          return (
            <article key={word.word} className="practice-word">
              <div className="practice-word-top">
                <div>
                  <strong>{word.word}</strong>
                  <p>{word.ipa ?? word.syllable_hint}</p>
                </div>
                {word.stress_syllable ? <span>Stress {word.stress_syllable}</span> : null}
              </div>
              <p>{word.reason}</p>
              <details className="practice-details">
                <summary>Show practice</summary>
                <div className="practice-detail-copy">
                  <p><strong>How to practice:</strong> {word.drill}</p>
                </div>
              </details>
              <div className="button-row">
                <button className="ghost-button" type="button" onClick={() => speak(word.native_pronunciation ?? word.word, 0.92)}>
                  Native pronunciation
                </button>
                <button className="ghost-button" type="button" onClick={() => speak(word.slow_pronunciation ?? word.word, 0.62)}>
                  Slow pronunciation
                </button>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => setRepetitionCounts((current) => ({ ...current, [word.word]: Math.min(word.repetitions, count + 1) }))}
                >
                  Repeat
                </button>
              </div>
              <div className="repeat-track" aria-label={`${count} of ${word.repetitions} repetitions completed`}>
                {Array.from({ length: word.repetitions }).map((_, index) => (
                  <span key={`${word.word}-${index}`} className={`repeat-dot ${index < count ? "filled" : ""}`} />
                ))}
              </div>
            </article>
          );
        })}
      </div>

      <div className="practice-sentences">
        <div className="section-header">
          <div>
            <span className="small-label">Practice sentences</span>
            <h4>Use the words in natural spoken English</h4>
          </div>
        </div>
        {practicePlan.sentences.map((sentence) => (
          <article key={sentence.sentence} className="sentence-row">
            <p>{sentence.sentence}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
