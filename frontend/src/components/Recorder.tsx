import { useEffect, useRef, useState } from "react";

import { MAX_SECONDS, MIN_SECONDS } from "../lib/audio";

type RecorderProps = {
  onReady: (file: File | null) => void;
};

export function Recorder({ onReady }: RecorderProps) {
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const animationRef = useRef<number | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const [isRecording, setIsRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [status, setStatus] = useState("Idle");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isRecording) {
      return;
    }

    const timer = window.setInterval(() => {
      setSeconds((value) => value + 1);
    }, 1000);

    return () => window.clearInterval(timer);
  }, [isRecording]);

  useEffect(() => {
    if (!isRecording) {
      return;
    }
    if (seconds < MIN_SECONDS) {
      setStatus(`Keep going - ${MIN_SECONDS - seconds}s until the minimum length`);
      return;
    }
    if (seconds < MAX_SECONDS) {
      setStatus(`Perfect range - ${MAX_SECONDS - seconds}s remaining`);
      return;
    }
    setStatus("Maximum duration reached. Finalizing recording...");
    stopRecording();
  }, [isRecording, seconds]);

  useEffect(() => {
    return () => {
      cleanup();
    };
  }, []);

  function cleanup() {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    audioContextRef.current?.close().catch(() => undefined);
    if (animationRef.current) {
      window.cancelAnimationFrame(animationRef.current);
    }
    streamRef.current = null;
    audioContextRef.current = null;
    analyserRef.current = null;
    animationRef.current = null;
  }

  function drawWaveform() {
    const canvas = canvasRef.current;
    const analyser = analyserRef.current;
    if (!canvas || !analyser) {
      return;
    }
    const ctx = canvas.getContext("2d");
    if (!ctx) {
      return;
    }

    const data = new Uint8Array(analyser.frequencyBinCount);
    const render = () => {
      if (!analyserRef.current) {
        return;
      }
      analyser.getByteFrequencyData(data);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = "rgba(15, 23, 42, 0.08)";
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      const bars = 32;
      const barWidth = canvas.width / bars;
      for (let index = 0; index < bars; index += 1) {
        const value = data[index * 2] ?? 0;
        const height = (value / 255) * canvas.height;
        const x = index * barWidth;
        const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height);
        gradient.addColorStop(0, "#ef4444");
        gradient.addColorStop(0.5, "#f59e0b");
        gradient.addColorStop(1, "#22c55e");
        ctx.fillStyle = gradient;
        ctx.fillRect(x + 3, canvas.height - height, Math.max(6, barWidth - 6), height);
      }
      animationRef.current = window.requestAnimationFrame(render);
    };
    render();
  }

  async function startRecording() {
    setError("");
    setSeconds(0);
    setStatus("Requesting microphone...");
    onReady(null);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "audio/webm";
      const recorder = new MediaRecorder(stream, { mimeType });
      const audioContext = new AudioContext();
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 128;
      const source = audioContext.createMediaStreamSource(stream);
      source.connect(analyser);

      streamRef.current = stream;
      mediaRecorderRef.current = recorder;
      audioContextRef.current = audioContext;
      analyserRef.current = analyser;
      chunksRef.current = [];

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        const file = new File([blob], `recording-${Date.now()}.webm`, { type: "audio/webm" });
        onReady(file);
        cleanup();
      };

      recorder.start(250);
      setIsRecording(true);
      setStatus("Recording live");
      drawWaveform();
    } catch {
      setStatus("Microphone unavailable");
      setError("Microphone access failed. You can still upload an existing file.");
    }
  }

  function stopRecording() {
    if (!mediaRecorderRef.current || mediaRecorderRef.current.state === "inactive") {
      return;
    }
    mediaRecorderRef.current.stop();
    setIsRecording(false);
  }

  const isValidWindow = seconds >= MIN_SECONDS && seconds <= MAX_SECONDS;
  const remaining = Math.max(0, MAX_SECONDS - seconds);

  return (
    <div className="recorder-card">
      <div className="recorder-topline">
        <div>
          <span className="micro-label">Record audio</span>
          <strong>{isRecording ? "Microphone live" : "Ready to record"}</strong>
        </div>
        <span className={`recording-chip ${isRecording ? "active" : ""}`}>{isRecording ? "Recording" : "Standby"}</span>
      </div>

      <canvas ref={canvasRef} width={560} height={88} className="waveform" aria-hidden="true" />

      <div className="recorder-metrics">
        <div>
          <span>Elapsed</span>
          <strong>{seconds}s</strong>
        </div>
        <div>
          <span>Remaining</span>
          <strong>{remaining}s</strong>
        </div>
        <div>
          <span>Status</span>
          <strong>{status}</strong>
        </div>
        <div>
          <span>Validation</span>
          <strong>{isValidWindow ? "Valid length" : "Too short"}</strong>
        </div>
      </div>

      <div className="button-row">
        <button className="secondary-button" type="button" onClick={startRecording} disabled={isRecording}>
          Start recording
        </button>
        <button className="ghost-button" type="button" onClick={stopRecording} disabled={!isRecording}>
          Stop recording
        </button>
      </div>

      <p className={`validation-copy ${isValidWindow ? "valid" : ""}`}>
        {isValidWindow
          ? "Great. This recording is within the required 30 to 45 second window."
          : `Record between ${MIN_SECONDS} and ${MAX_SECONDS} seconds so analysis can begin.`}
      </p>
      {error ? <p className="error-text">{error}</p> : null}
    </div>
  );
}
