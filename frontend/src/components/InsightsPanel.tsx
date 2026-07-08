import type { CoachInsight } from "../types/assessment";

type InsightsPanelProps = {
  insights: CoachInsight[];
};

export function InsightsPanel({ insights }: InsightsPanelProps) {
  return (
    <section className="insights-card">
      <div className="section-copy">
        <span className="section-kicker">AI insights</span>
        <h3>What the coach noticed about your speaking habits</h3>
      </div>
      <div className="insights-grid">
        {insights.map((insight) => (
          <article key={insight.title} className="insight-card">
            <span>{insight.title}</span>
            <strong>{insight.value}</strong>
            <p>{insight.description}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
