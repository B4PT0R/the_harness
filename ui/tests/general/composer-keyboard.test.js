import test from "node:test";
import assert from "node:assert/strict";
import { handleComposerKeyDown } from "../../src/composer-keyboard.js";

function press(overrides = {}, canSubmit = true) {
  let prevented = 0;
  let submitted = 0;
  handleComposerKeyDown({
    key: "Enter", currentTarget: { form: { requestSubmit() { submitted++; } } },
    preventDefault() { prevented++; }, ...overrides,
  }, canSubmit);
  return { prevented, submitted };
}

test("Enter submits via the form and suppresses the newline", () => {
  assert.deepEqual(press(), { prevented: 1, submitted: 1 });
});
test("touch-first Return retains native newline behavior even when sending is unavailable", () => {
  const currentTarget = {
    ownerDocument: { defaultView: { matchMedia(query) {
      assert.equal(query, "(pointer: coarse)");
      return { matches: true };
    } } },
    form: { requestSubmit: assert.fail },
  };
  for (const canSubmit of [true, false]) {
    assert.deepEqual(press({ currentTarget }, canSubmit), { prevented: 0, submitted: 0 });
  }
});
test("desktop with a fine primary pointer still sends with Enter", () => {
  let submitted = 0;
  const currentTarget = {
    ownerDocument: { defaultView: { matchMedia: () => ({ matches: false }) } },
    form: { requestSubmit() { submitted++; } },
  };
  assert.deepEqual(press({ currentTarget }), { prevented: 1, submitted: 0 });
  assert.equal(submitted, 1);
});
test("Shift+Enter and other modified keys retain native behavior", () => {
  for (const overrides of [{ shiftKey: true }, { ctrlKey: true }, { altKey: true }, { metaKey: true }, { key: "a" }]) {
    assert.deepEqual(press(overrides), { prevented: 0, submitted: 0 });
  }
});
test("IME confirmation never sends a message", () => {
  for (const overrides of [{ isComposing: true }, { nativeEvent: { isComposing: true } }, { keyCode: 229 }]) {
    assert.deepEqual(press(overrides), { prevented: 0, submitted: 0 });
  }
});
test("disabled submission and held Enter do not send", () => {
  assert.deepEqual(press({}, false), { prevented: 1, submitted: 0 });
  assert.deepEqual(press({ repeat: true }), { prevented: 1, submitted: 0 });
});
