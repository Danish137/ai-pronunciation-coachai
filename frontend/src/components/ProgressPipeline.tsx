type ProgressPipelineProps = {
  steps: readonly string[];
  stepIndex: number;
  visible: boolean;
};

export function ProgressPipeline({ steps, stepIndex, visible }: ProgressPipelineProps) {
  if (!visible) {
    return null;
  }

  return (
    <section className="progress-card" aria-live="polite">
      <div className="section-copy">
        <span className="section-kicker">AI Coach is working</span>
        <h3>Turning your recording into a practice plan</h3>
      </div>
      <div className="progress-track" />
      <div className="progress-steps">
        {steps.map((step, index) => {
          const state = index < stepIndex ? "done" : index === stepIndex ? "active" : "idle";
          return (
            <div key={step} className={`progress-step ${state}`}>
              <span className="progress-dot" />
              <div>
                <strong>{step}</strong>
                <p>{index === stepIndex ? "In progress now" : index < stepIndex ? "Completed" : "Queued next"}</p>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
