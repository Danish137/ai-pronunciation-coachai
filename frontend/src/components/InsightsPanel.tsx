import type { CoachInsight } from "../types/assessment";

type InsightsPanelProps = {
  insights: CoachInsight[];
};

export function InsightsPanel({ insights }: InsightsPanelProps) {
  return (
    <section className="insights-card">
      <div className="section-header">
        <div>
          <span className="small-label">Speaking patterns</span>
          <h3>Useful habits to notice</h3>
        </div>
      </div>
      <div className="insights-list">
        {insights.map((insight) => (
          <article key={insight.title} className="insight-row">
            <div>
              <strong>{insight.title}</strong>
              <p>{insight.description}</p>
            </div>
            <span>{insight.value}</span>
          </article>
        ))}
      </div>
    </section>
  );
}
