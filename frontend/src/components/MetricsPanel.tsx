import type { MetricInsight } from "../types/assessment";

type MetricsPanelProps = {
  metrics: MetricInsight[];
};

export function MetricsPanel({ metrics }: MetricsPanelProps) {
  return (
    <section className="metrics-card">
      <div className="section-header">
        <div>
          <span className="small-label">Detailed analytics</span>
          <h3>Compact score breakdown</h3>
        </div>
      </div>
      <div className="metrics-list">
        {metrics.map((metric) => (
          <article key={metric.key} className="metric-row">
            <div>
              <strong>{metric.label}</strong>
              <p>{metric.explanation}</p>
            </div>
            <span>{Math.round(metric.score)}</span>
          </article>
        ))}
      </div>
    </section>
  );
}
