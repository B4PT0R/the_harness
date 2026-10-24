// One cancellable recording/transcription attempt. Never submits a chat message.
export const MAX_DICTATION_MS = 120_000;
export const MAX_AUDIO_BYTES = 10 * 1024 * 1024;
const formats = ["audio/webm;codecs=opus", "audio/mp4", "audio/ogg;codecs=opus", "audio/webm"];

export function dictationSupported() {
  return Boolean(globalThis.navigator?.mediaDevices?.getUserMedia && globalThis.MediaRecorder
    && (globalThis.AudioContext || globalThis.webkitAudioContext) && globalThis.OfflineAudioContext);
}

// Decode the browser's recording locally; upload only mono PCM16LE at 24 kHz.
export async function dictationPCM(blob, signal, {
  Context = globalThis.AudioContext || globalThis.webkitAudioContext,
  OfflineContext = globalThis.OfflineAudioContext,
} = {}) {
  signal.throwIfAborted();
  const context = new Context();
  let decoded;
  try { decoded = await context.decodeAudioData(await blob.arrayBuffer()); }
  finally { await context.close(); }
  signal.throwIfAborted();
  if (!decoded.length) throw new Error("dictationEmpty");
  const frames = Math.ceil(decoded.duration * 24_000);
  if (frames > 120 * 24_000) throw new Error("dictationTooLarge");
  const offline = new OfflineContext(1, frames, 24_000);
  const source = offline.createBufferSource();
  source.buffer = decoded;
  source.connect(offline.destination);
  source.start();
  const rendered = await offline.startRendering();
  signal.throwIfAborted();
  const samples = rendered.getChannelData(0);
  const pcm = new DataView(new ArrayBuffer(samples.length * 2));
  for (let i = 0; i < samples.length; i++) {
    const sample = Math.max(-1, Math.min(1, samples[i]));
    pcm.setInt16(i * 2, Math.round(sample * (sample < 0 ? 32768 : 32767)), true);
  }
  return new Blob([pcm.buffer], { type: "audio/pcm" });
}

export function appendDictation(draft, text) {
  return draft + (draft && !/\s$/.test(draft) ? " " : "") + text;
}

export function createDictation({ transcribe, onText, onState, onError,
  mediaDevices = globalThis.navigator?.mediaDevices, Recorder = globalThis.MediaRecorder,
  maxDuration = MAX_DICTATION_MS }) {
  let attempt, disposed = false;
  const change = state => { if (!disposed) onState(state); };
  const release = current => {
    clearTimeout(current.timer);
    current.stream?.getTracks().forEach(track => track.stop());
  };
  function cancel() {
    const current = attempt;
    attempt = null;
    if (current) {
      current.controller.abort();
      if (current.recorder?.state !== "inactive") current.recorder?.stop();
      release(current);
    }
    change("idle");
  }
  function fail(current, error) {
    if (attempt !== current) return;
    cancel();
    if (!disposed) onError(error);
  }
  function stop() {
    const current = attempt;
    if (!current || current.recorder?.state !== "recording") return;
    change("transcribing");
    current.recorder.stop();
    release(current);
  }
  async function start() {
    if (disposed || attempt) return;
    const current = { controller: new AbortController(), chunks: [], size: 0 };
    attempt = current;
    change("requesting");
    try {
      current.stream = await mediaDevices.getUserMedia({ audio: true });
      if (attempt !== current) { release(current); return; }
      const mimeType = formats.find(type => Recorder.isTypeSupported(type));
      current.recorder = new Recorder(current.stream, mimeType ? { mimeType } : undefined);
      const recorder = current.recorder;
      recorder.ondataavailable = event => {
        if (attempt !== current || !event.data.size) return;
        current.size += event.data.size;
        if (current.size > MAX_AUDIO_BYTES) {
          fail(current, new Error("dictationTooLarge"));
        } else current.chunks.push(event.data);
      };
      recorder.onerror = () => fail(current, new Error("dictationFailed"));
      recorder.onstop = async () => {
        release(current);
        if (attempt !== current) return;
        change("transcribing");
        try {
          const audio = new Blob(current.chunks, { type: recorder.mimeType });
          if (!audio.size) throw new Error("dictationEmpty");
          const text = await transcribe(audio, current.controller.signal);
          if (attempt !== current) return;
          if (!text?.trim()) throw new Error("dictationEmpty");
          attempt = null;
          change("idle");
          onText(text.trim());
        } catch (error) { fail(current, error); }
      };
      recorder.start(1000);
      if (attempt !== current) return;
      change("recording");
      current.timer = setTimeout(stop, maxDuration);
    } catch (error) { fail(current, error); }
  }
  return { start, stop, cancel, dispose() { disposed = true; cancel(); } };
}
