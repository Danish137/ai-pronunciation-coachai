import { useDeferredValue, useMemo, useState } from "react";

import type { WordFeedback } from "../types/assessment";

type FilterValue = "all" | "needs-practice" | "good" | "excellent";

type TranscriptViewerProps = {
  words: WordFeedback[];
  selectedStartMs: number | null;
  onSelectWord: (word: WordFeedback) => void;
};

const FILTER_OPTIONS: { value: FilterValue; label: string }[] = [
  { value: "all", label: "All" },
  { value: "needs-practice", label: "Needs Practice" },
  { value: "good", label: "Good" },
  { value: "excellent", label: "Excellent" },
];

export function TranscriptViewer({ words, selectedStartMs, onSelectWord }: TranscriptViewerProps) {
  const [filter, setFilter] = useState<FilterValue>("all");
  const [search, setSearch] = useState("");
  const [detailsExpanded, setDetailsExpanded] = useState(false);
  const deferredSearch = useDeferredValue(search);

  const filteredWords = useMemo(() => {
    return words.filter((word) => {
      const matchesFilter =
        filter === "all"
          ? true
          : filter === "needs-practice"
            ? word.status === "watch" || word.status === "needs-practice"
            : word.status === filter;

      const matchesSearch = deferredSearch.trim()
        ? word.word.toLowerCase().includes(deferredSearch.trim().toLowerCase())
        : true;

      return matchesFilter && matchesSearch;
    });
  }, [deferredSearch, filter, words]);

  const selectedWord = filteredWords.find((word) => word.start_ms === selectedStartMs) ?? words.find((word) => word.start_ms === selectedStartMs) ?? null;

  function explanationForWord(word: WordFeedback) {
    if (word.pronunciation_explanation) {
      return word.pronunciation_explanation;
    }
    if (word.evidence_summary) {
      return word.evidence_summary;
    }
    if (word.issue) {
      return word.issue;
    }
    if (word.affected_syllable && word.affected_phonemes?.length) {
      return `The ${word.affected_syllable} part of ${word.word} was less stable, especially around ${word.affected_phonemes.slice(0, 2).join(" and ")}.`;
    }
    return `This word was understandable, but it did not sound as clear or consistent as your stronger words.`;
  }

  function suggestionForWord(word: WordFeedback) {
    if (word.suggestion) {
      return word.suggestion;
    }
    if (word.affected_syllable) {
      return `Practice the ${word.affected_syllable} part of ${word.word} slowly, then say the full word again in a short phrase.`;
    }
    if (word.affected_phonemes?.length) {
      return `Repeat ${word.word} while emphasizing ${word.affected_phonemes.slice(0, 2).join(" and ")}, then place it back into a sentence.`;
    }
    return `Try ${word.word} once slowly, once naturally, and once in a sentence so the sound stays consistent.`;
  }

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
    <section className="transcript-card">
      <div className="section-header">
        <div>
          <span className="small-label">Interactive transcript</span>
          <h3>Tap any word to understand what needs work</h3>
        </div>
      </div>

      <div className="transcript-toolbar">
        <div className="filter-row" role="tablist" aria-label="Transcript filters">
          {FILTER_OPTIONS.map((option) => (
            <button
              key={option.value}
              className={`filter-chip ${filter === option.value ? "active" : ""}`}
              type="button"
              onClick={() => setFilter(option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>
        <input
          className="transcript-search"
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search a word"
          aria-label="Search transcript"
        />
      </div>

      <div className="transcript-flow">
        {filteredWords.map((word) => (
          <button
            key={`${word.word}-${word.start_ms}`}
            className={`word-pill ${word.status} ${selectedStartMs === word.start_ms ? "selected" : ""}`}
            type="button"
            onClick={() => onSelectWord(word)}
          >
            {word.word}
          </button>
        ))}
      </div>

      {selectedWord ? (
        <article className={`word-drawer ${selectedWord.status}`}>
          <div className="word-drawer-header">
            <div>
              <span className="small-label">Word detail</span>
              <h4>{selectedWord.word}</h4>
            </div>
            <strong>{Math.round(selectedWord.score)}/100</strong>
          </div>
          <div className="word-detail-grid">
            <p><strong>Detected weakness:</strong> {explanationForWord(selectedWord)}</p>
            <p><strong>Practice suggestion:</strong> {suggestionForWord(selectedWord)}</p>
            {selectedWord.ipa ? <p><strong>Expected pronunciation:</strong> {selectedWord.ipa}</p> : null}
            {selectedWord.syllables.length ? <p><strong>Syllables:</strong> {selectedWord.syllables.join(" • ")}</p> : null}
            {selectedWord.stress_syllable ? <p><strong>Stress:</strong> syllable {selectedWord.stress_syllable}</p> : null}
            {selectedWord.phoneme_hint ? <p><strong>Sounds to watch:</strong> {selectedWord.phoneme_hint}</p> : null}
          </div>
          <div className="button-row">
            <button className="ghost-button" type="button" onClick={() => speak(selectedWord.native_pronunciation ?? selectedWord.word, 0.92)}>
              Native pronunciation
            </button>
            <button className="ghost-button" type="button" onClick={() => speak(selectedWord.slow_pronunciation ?? selectedWord.word, 0.62)}>
              Slow pronunciation
            </button>
            <button className="secondary-button" type="button" onClick={() => onSelectWord(selectedWord)}>
              Retry this word
            </button>
          </div>
        </article>
      ) : null}

      <div className="collapse-block">
        <button className="ghost-button" type="button" onClick={() => setDetailsExpanded((value) => !value)}>
          {detailsExpanded ? "Hide detailed analytics" : "Show detailed analytics"}
        </button>
        {detailsExpanded ? (
          <div className="word-analysis-grid">
            {filteredWords.map((word) => (
              <article key={`${word.word}-${word.start_ms}-detail`} className={`analysis-card ${word.status}`}>
                <div className="analysis-topline">
                  <strong>{word.word}</strong>
                  <span>{Math.round(word.score)}</span>
                </div>
                <p>{explanationForWord(word)}</p>
                <small>{suggestionForWord(word)}</small>
              </article>
            ))}
          </div>
        ) : null}
      </div>
    </section>
  );
}
