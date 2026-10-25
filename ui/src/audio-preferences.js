// Playback balance belongs to this browser/device, not the shared agent config.
export const ttsVolumeKey = "the-harness.tts-autoplay-volume";
function storedVolume() {
  try {
    const raw = globalThis.localStorage?.getItem(ttsVolumeKey);
    const value = raw === null || raw === undefined || raw.trim() === "" ? NaN : Number(raw);
    return Number.isFinite(value) && value >= 0 && value <= 1 ? value : 1;
  } catch { return 1; }
}
let volume = storedVolume();
const listeners = new Set();
export const getTtsVolume = () => volume;
function update(value) {
  volume = value;
  for (const listener of listeners) listener(volume);
}
export function setTtsVolume(value) {
  if (!Number.isFinite(value)) return;
  const next = Math.max(0, Math.min(1, value));
  try { globalThis.localStorage?.setItem(ttsVolumeKey, String(next)); } catch { /* Session-only if storage is unavailable. */ }
  update(next);
}
export function subscribeTtsVolume(listener) {
  listeners.add(listener);
  function storage(event) {
    if (event.key === ttsVolumeKey || event.key === null) {
      volume = storedVolume();
      listener(volume);
    }
  }
  globalThis.addEventListener?.("storage", storage);
  return () => {
    listeners.delete(listener);
    globalThis.removeEventListener?.("storage", storage);
  };
}
