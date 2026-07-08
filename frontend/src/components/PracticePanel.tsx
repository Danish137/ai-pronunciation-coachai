import { useState } from "react";

import type { PracticePlan } from "../types/assessment";

type PracticePanelProps = {
  practicePlan: PracticePlan;
};

export function PracticePanel({ practicePlan }: PracticePanelProps) {
  const [completedWords, setCompletedWords] = useState<Record<string, boolean>>({});

  function speakWord(word: string) {
    if (!("speechSynthesis" in window)) {
      return;
    }
    const utterance = new SpeechSynthesisUtterance(word);
    utterance.rate = 0.78;
    utterance.lang = "en-US";
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
  }

  return (
    <section className="practice-card">
      <div className="section-copy">
        <span className="section-kicker">Today's practice</span>
        <h3>{practicePlan.today_focus}</h3>
        <p>
          Estimated score if fixed: <strong>{practicePlan.estimated_score_if_fixed}</strong>
          {" "}({practicePlan.estimated_gain >= 0 ? `+${practicePlan.estimated_gain}` : practicePlan.estimated_gain})
        </p>
      </div>

      <div className="practice-words">
        {practicePlan.words.map((word) => (
          <article key={word.word} className={`practice-word ${completedWords[word.word] ? "completed" : ""}`}>
            <div className="practice-word-top">
              <div>
                <strong>{word.word}</strong>
                <p>{word.syllable_hint}</p>
              </div>
              <span>+{word.estimated_gain}</span>
            </div>
            <p>{word.reason}</p>
            <p><strong>Drill:</strong> {word.drill}</p>
            <div className="button-row">
              <button className="ghost-button" type="button" onClick={() => speakWord(word.word)}>
                Hear pronunciation
              </button>
              <button
                className="secondary-button"
                type="button"
                onClick={() => setCompletedWords((current) => ({ ...current, [word.word]: !current[word.word] }))}
              >
                {completedWords[word.word] ? "Practiced" : `Repeat x${word.repetitions}`}
              </button>
            </div>
          </article>
        ))}
      </div>

      <div className="practice-sentences">
        <div className="section-copy">
          <span className="section-kicker">Practice sentences</span>
          <h4>Transfer the improvement into connected speech</h4>
        </div>
        {practicePlan.sentences.map((sentence) => (
          <article key={sentence.sentence} className="sentence-card">
            <p>{sentence.sentence}</p>
            <small>Focus words: {sentence.focus_words.join(", ")}</small>
          </article>
        ))}
      </div>
    </section>
  );
}
