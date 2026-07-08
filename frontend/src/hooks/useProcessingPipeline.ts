import { useEffect, useState } from "react";

const PROCESS_STEPS = [
  "Uploading audio...",
  "Normalizing audio...",
  "Analyzing pronunciation...",
  "Generating personalized coaching...",
  "Done",
] as const;

export function useProcessingPipeline(active: boolean) {
  const [stepIndex, setStepIndex] = useState(0);

  useEffect(() => {
    if (!active) {
      setStepIndex(0);
      return;
    }

    setStepIndex(0);
    const timers = [
      window.setTimeout(() => setStepIndex(1), 700),
      window.setTimeout(() => setStepIndex(2), 1800),
      window.setTimeout(() => setStepIndex(3), 3600),
    ];

    return () => {
      timers.forEach((timer) => window.clearTimeout(timer));
    };
  }, [active]);

  return {
    steps: PROCESS_STEPS,
    stepIndex,
  };
}
