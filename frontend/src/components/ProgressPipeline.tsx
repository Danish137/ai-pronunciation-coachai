import type { PipelineStep } from "../hooks/useProcessingPipeline";

type ProgressPipelineProps = {
  steps: readonly PipelineStep[];
  stepIndex: number;
  progressPct: number;
  visible: boolean;
};

export function ProgressPipeline({ steps, stepIndex, progressPct, visible }: ProgressPipelineProps) {
  if (!visible) return null;

  const current = steps[stepIndex];

  return (
    <section className="progress-card" aria-live="polite">
      <div className="progress-milestones">
        {steps.map((step, i) => (
          <div
            key={step.label}
            className={`milestone ${i < stepIndex ? "done" : i === stepIndex ? "active" : ""}`}
          >
            <span className="milestone-dot" />
            <span className="milestone-label">{step.label}</span>
          </div>
        ))}
      </div>
      <div className="progress-bar-shell" aria-hidden="true">
        <div
          className="progress-bar-fill"
          style={{ width: `${progressPct}%`, transition: "width 0.8s ease" }}
        />
      </div>
      <p className="progress-current-label">{current?.label ?? "Processing…"}</p>
    </section>
  );
}
