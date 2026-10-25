import test from "node:test";
import assert from "node:assert/strict";

let version = 0;
async function preference(raw = null, unavailable = false) {
  const previous = Object.getOwnPropertyDescriptor(globalThis, "localStorage");
  let saved = raw;
  Object.defineProperty(globalThis, "localStorage", { configurable: true, value: {
    getItem() { if (unavailable) throw new Error("blocked"); return saved; },
    setItem(key, value) { if (unavailable) throw new Error("blocked"); saved = value; },
  } });
  const module = await import(`../../src/audio-preferences.js?test=${version++}`);
  return { ...module, saved: () => saved, restore() {
    if (previous) Object.defineProperty(globalThis, "localStorage", previous);
    else delete globalThis.localStorage;
  } };
}

test("restores valid volume including mute, otherwise preserves the 100% default", async () => {
  for (const [raw, expected] of [[null, 1], ["", 1], ["0", 0], ["0.35", 0.35], ["1", 1], ["garbage", 1], ["-1", 1], ["2", 1]]) {
    const p = await preference(raw);
    try { assert.equal(p.getTtsVolume(), expected); } finally { p.restore(); }
  }
});

test("persists bounded values, notifies live listeners and removes subscriptions", async () => {
  const p = await preference();
  try {
    const updates = [];
    const unsubscribe = p.subscribeTtsVolume(value => updates.push(value));
    p.setTtsVolume(0.35);
    assert.equal(p.saved(), "0.35");
    assert.equal(p.getTtsVolume(), 0.35);
    p.setTtsVolume(-4);
    p.setTtsVolume(5);
    p.setTtsVolume(NaN);
    assert.deepEqual(updates, [0.35, 0, 1]);
    unsubscribe();
    p.setTtsVolume(0.5);
    assert.deepEqual(updates, [0.35, 0, 1]);
  } finally { p.restore(); }
});

test("works for this session when browser storage is blocked", async () => {
  const p = await preference(null, true);
  try {
    assert.equal(p.getTtsVolume(), 1);
    p.setTtsVolume(0.2);
    assert.equal(p.getTtsVolume(), 0.2);
  } finally { p.restore(); }
});
