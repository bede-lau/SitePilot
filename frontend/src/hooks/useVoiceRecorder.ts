import { useCallback, useRef, useState } from "react";

export type RecorderStatus = "idle" | "requesting" | "recording" | "processing" | "denied" | "error";

/**
 * Press-and-hold voice capture: mic permission → MediaRecorder + an AnalyserNode driving a live
 * amplitude level for the waveform UI. Consumers get a Blob back from `stopAndGetBlob` to upload;
 * `cancel` discards it. Permission denial surfaces as a real status + message, never a silent no-op.
 */
export function useVoiceRecorder() {
  const [status, setStatus] = useState<RecorderStatus>("idle");
  const [level, setLevel] = useState(0); // 0..1 current amplitude, for the waveform
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const rafRef = useRef<number | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const teardownAudio = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;
    audioCtxRef.current?.close().catch(() => {});
    audioCtxRef.current = null;
    analyserRef.current = null;
  }, []);

  const start = useCallback(async (): Promise<boolean> => {
    setErrorMessage(null);
    setStatus("requesting");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const AudioCtxCtor =
        window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (AudioCtxCtor) {
        const ctx = new AudioCtxCtor();
        audioCtxRef.current = ctx;
        const source = ctx.createMediaStreamSource(stream);
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 256;
        source.connect(analyser);
        analyserRef.current = analyser;

        // A locally-scoped recursive tick — not a hook value — so the rAF loop's self-reference
        // never has to cross renders.
        function tick() {
          const currentAnalyser = analyserRef.current;
          if (!currentAnalyser) return;
          const data = new Uint8Array(currentAnalyser.frequencyBinCount);
          currentAnalyser.getByteTimeDomainData(data);
          let sumSquares = 0;
          for (let i = 0; i < data.length; i++) {
            const centered = (data[i] - 128) / 128;
            sumSquares += centered * centered;
          }
          const rms = Math.sqrt(sumSquares / data.length);
          setLevel(Math.min(1, rms * 4));
          rafRef.current = requestAnimationFrame(tick);
        }
        rafRef.current = requestAnimationFrame(tick);
      }

      const preferredMimeType = "audio/webm";
      const mimeType = window.MediaRecorder?.isTypeSupported?.(preferredMimeType) ? preferredMimeType : undefined;
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      mediaRecorderRef.current = recorder;
      recorder.start();
      setStatus("recording");
      return true;
    } catch (err) {
      teardownAudio();
      const name = err instanceof DOMException ? err.name : "";
      if (name === "NotAllowedError" || name === "SecurityError") {
        setStatus("denied");
        setErrorMessage("Microphone access denied — allow microphone permission in your browser to record a voice note.");
      } else {
        setStatus("error");
        setErrorMessage("Couldn't access the microphone on this device.");
      }
      return false;
    }
  }, [teardownAudio]);

  const finishRecording = useCallback((): Promise<Blob | null> => {
    return new Promise((resolve) => {
      const recorder = mediaRecorderRef.current;
      if (!recorder || recorder.state === "inactive") {
        resolve(null);
        return;
      }
      recorder.onstop = () => {
        const blob = chunksRef.current.length ? new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" }) : null;
        chunksRef.current = [];
        resolve(blob);
      };
      recorder.stop();
    });
  }, []);

  const stopAndGetBlob = useCallback(async (): Promise<Blob | null> => {
    setStatus("processing");
    const blob = await finishRecording();
    teardownAudio();
    setStatus("idle");
    setLevel(0);
    return blob;
  }, [finishRecording, teardownAudio]);

  const cancel = useCallback(async () => {
    await finishRecording();
    teardownAudio();
    setStatus("idle");
    setLevel(0);
  }, [finishRecording, teardownAudio]);

  return { status, level, errorMessage, start, stopAndGetBlob, cancel };
}
