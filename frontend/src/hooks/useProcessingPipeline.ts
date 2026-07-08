import { useEffect, useState } from "react";

const PROCESS_STEPS = [
  "Uploading recording...",
  "Understanding your speech...",
  "Finding pronunciation mistakes...",
  "Preparing your coaching plan...",
  "Almost ready...",
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
      window.setTimeout(() => setStepIndex(1), 650),
      window.setTimeout(() => setStepIndex(2), 1650),
      window.setTimeout(() => setStepIndex(3), 2900),
      window.setTimeout(() => setStepIndex(4), 4300),
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
