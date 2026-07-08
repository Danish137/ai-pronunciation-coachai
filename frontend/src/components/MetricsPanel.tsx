import type { MetricInsight } from "../types/assessment";

type MetricsPanelProps = {
  metrics: MetricInsight[];
};

export function MetricsPanel({ metrics }: MetricsPanelProps) {
  return (
    <section className="metrics-card">
      <div className="section-copy">
        <span className="section-kicker">Performance metrics</span>
        <h3>Numbers only where they help coaching</h3>
      </div>
      <div className="metrics-grid">
        {metrics.map((metric) => (
          <article key={metric.key} className="metric-card">
            <div className="metric-topline">
              <div>
                <strong>{metric.label}</strong>
                <p>{metric.band}</p>
              </div>
              <span>{Math.round(metric.score)}</span>
            </div>
            <p>{metric.explanation}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
