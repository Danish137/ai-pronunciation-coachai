type ProgressPipelineProps = {
  steps: readonly string[];
  stepIndex: number;
  visible: boolean;
};

export function ProgressPipeline({ steps, stepIndex, visible }: ProgressPipelineProps) {
  if (!visible) {
    return null;
  }

  const progress = ((stepIndex + 1) / steps.length) * 100;

  return (
    <section className="progress-card" aria-live="polite">
      <div className="progress-copy">
        <strong>{steps[stepIndex]}</strong>
        <p>Please wait a moment while we prepare your coaching report.</p>
      </div>
      <div className="progress-bar-shell" aria-hidden="true">
        <div className="progress-bar-fill" style={{ width: `${progress}%` }} />
      </div>
    </section>
  );
}
