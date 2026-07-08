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

  return (
    <section className="transcript-card">
      <div className="section-copy">
        <span className="section-kicker">Transcript coach</span>
        <h3>Review the words that matter</h3>
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
          placeholder="Search transcript"
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
              <span className="section-kicker">Selected word</span>
              <h4>{selectedWord.word}</h4>
            </div>
            <strong>{Math.round(selectedWord.score)}/100</strong>
          </div>
          <p>{selectedWord.issue}</p>
          <p><strong>How to improve:</strong> {selectedWord.suggestion}</p>
          <div className="word-drawer-meta">
            <span>{selectedWord.practice_priority} priority</span>
            <span>{selectedWord.confidence} confidence</span>
            {selectedWord.phoneme_hint ? <span>Watch {selectedWord.phoneme_hint}</span> : null}
          </div>
        </article>
      ) : null}

      <div className="collapse-block">
        <button className="ghost-button" type="button" onClick={() => setDetailsExpanded((value) => !value)}>
          {detailsExpanded ? "Collapse detailed word analysis" : "Expand detailed word analysis"}
        </button>
        {detailsExpanded ? (
          <div className="word-analysis-grid">
            {filteredWords.map((word) => (
              <article key={`${word.word}-${word.start_ms}-detail`} className={`analysis-card ${word.status}`}>
                <div className="analysis-topline">
                  <strong>{word.word}</strong>
                  <span>{Math.round(word.score)}</span>
                </div>
                <p>{word.issue}</p>
                <small>{word.suggestion}</small>
              </article>
            ))}
          </div>
        ) : null}
      </div>
    </section>
  );
}
