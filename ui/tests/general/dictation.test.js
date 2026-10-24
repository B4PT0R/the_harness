import test from "node:test";
import assert from "node:assert/strict";
import { appendDictation, createDictation, dictationPCM, MAX_AUDIO_BYTES } from "../../src/dictation.js";

const tick = () => new Promise(resolve => setTimeout(resolve, 0));
function setup({ transcribe = async () => "Bonjour !", getUserMedia, maxDuration } = {}) {
  const states = [], texts = [], errors = [], calls = [];
  const track = { stopped: false, stop() { this.stopped = true; } };
  class Recorder {
    static isTypeSupported(type) { return type.startsWith("audio/webm"); }
    constructor(stream, options) { this.state = "inactive"; this.mimeType = options.mimeType; }
    start() { this.state = "recording"; }
    stop() {
      this.state = "inactive";
      queueMicrotask(() => {
        this.ondataavailable({ data: new Blob(["audio"]) });
        this.onstop();
      });
    }
  }
  const session = createDictation({
    Recorder, mediaDevices: { getUserMedia: getUserMedia || (async () => ({ getTracks: () => [track] })) },
    transcribe: async (...args) => { calls.push(args); return transcribe(...args); },
    onState: value => states.push(value), onText: value => texts.push(value), onError: error => errors.push(error),
    ...(maxDuration !== undefined && { maxDuration }),
  });
  return { session, states, texts, errors, calls, track, Recorder };
}

test("record, stop microphone, transcribe once, return editable text without sending", async () => {
  const fixture = setup();
  await fixture.session.start();
  assert.equal(fixture.states.at(-1), "recording");
  fixture.session.stop();
  assert.equal(fixture.track.stopped, true);
  await tick();
  assert.deepEqual(fixture.texts, ["Bonjour !"]);
  assert.equal(fixture.calls.length, 1);
  assert.equal(fixture.calls[0][0].type, "audio/webm;codecs=opus");
  assert.equal(fixture.states.at(-1), "idle");
  assert.deepEqual(fixture.errors, []);
});

test("permission cancelled while pending releases the late microphone without recording", async () => {
  let grant;
  const fixture = setup({ getUserMedia: () => new Promise(resolve => { grant = resolve; }) });
  const pending = fixture.session.start();
  fixture.session.cancel();
  grant({ getTracks: () => [fixture.track] });
  await pending;
  assert.equal(fixture.track.stopped, true);
  assert.equal(fixture.states.at(-1), "idle");
  assert.equal(fixture.calls.length, 0);
});

test("cancelling transcription aborts the request and ignores late text", async () => {
  let resolve;
  const fixture = setup({ transcribe: () => new Promise(done => { resolve = done; }) });
  await fixture.session.start();
  fixture.session.stop();
  await tick();
  fixture.session.cancel();
  assert.equal(fixture.calls[0][1].aborted, true);
  resolve("Late result");
  await tick();
  assert.deepEqual(fixture.texts, []);
  assert.deepEqual(fixture.errors, []);
});

test("permission and backend errors are reported without adding text", async () => {
  for (const options of [
    { getUserMedia: async () => { throw new DOMException("Denied", "NotAllowedError"); } },
    { transcribe: async () => { throw new Error("Backend failed"); } },
    { transcribe: async () => "  " },
  ]) {
    const fixture = setup(options);
    await fixture.session.start();
    fixture.session.stop();
    await tick();
    assert.equal(fixture.states.at(-1), "idle");
    assert.equal(fixture.errors.length, 1);
    assert.deepEqual(fixture.texts, []);
  }
});

test("recording has a duration limit and disposal never transcribes", async () => {
  const fixture = setup({ maxDuration: 1 });
  await fixture.session.start();
  await new Promise(resolve => setTimeout(resolve, 15));
  assert.deepEqual(fixture.texts, ["Bonjour !"]);
  const disposed = setup();
  await disposed.session.start();
  disposed.session.dispose();
  await tick();
  assert.equal(disposed.track.stopped, true);
  assert.deepEqual(disposed.calls, []);
});

test("oversized audio is rejected before upload", async () => {
  const fixture = setup();
  const original = fixture.Recorder.prototype.start;
  fixture.Recorder.prototype.start = function () {
    original.call(this);
    this.ondataavailable({ data: new Blob([new Uint8Array(MAX_AUDIO_BYTES + 1)]) });
  };
  await fixture.session.start();
  await tick();
  assert.equal(fixture.errors[0].message, "dictationTooLarge");
  assert.deepEqual(fixture.calls, []);
  fixture.session.dispose();
});

test("dictation appends to the latest draft without erasing typed content", () => {
  assert.equal(appendDictation("", "Bonjour"), "Bonjour");
  assert.equal(appendDictation("Une idée", "et sa suite"), "Une idée et sa suite");
  assert.equal(appendDictation("Une idée\n", "suite"), "Une idée\nsuite");
});


test("WebAudio conversion resamples/downmixes and encodes clamped PCM16LE", async () => {
  let closed = false;
  class Context {
    async decodeAudioData(data) { assert.equal(data.byteLength, 5); return { duration: 4 / 24000, length: 4 }; }
    async close() { closed = true; }
  }
  class OfflineContext {
    constructor(channels, frames, rate) { assert.deepEqual([channels, frames, rate], [1, 4, 24000]); }
    createBufferSource() { return { connect() {}, start() {} }; }
    async startRendering() { return { getChannelData: () => new Float32Array([-2, -.5, .5, 2]) }; }
  }
  const pcm = await dictationPCM(new Blob(["audio"]), new AbortController().signal, { Context, OfflineContext });
  assert.equal(closed, true);
  assert.equal(pcm.type, "audio/pcm");
  const data = new DataView(await pcm.arrayBuffer());
  assert.deepEqual([0, 2, 4, 6].map(i => data.getInt16(i, true)), [-32768, -16384, 16384, 32767]);
});

test("conversion closes decoder on failure and respects cancellation", async () => {
  let closed = false;
  class Context {
    async decodeAudioData() { throw new Error("bad audio"); }
    async close() { closed = true; }
  }
  await assert.rejects(dictationPCM(new Blob(["x"]), new AbortController().signal, { Context }), /bad audio/);
  assert.equal(closed, true);
  const controller = new AbortController(); controller.abort();
  await assert.rejects(dictationPCM(new Blob(["x"]), controller.signal, { Context }), { name: "AbortError" });
});
