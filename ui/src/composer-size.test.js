import test from "node:test";
import assert from "node:assert/strict";
import { resizeComposerTextarea } from "./composer-size.js";

test("composer grows with content and shrinks when the draft clears", () => {
  const element = { style: {}, scrollHeight: 96 };
  const styles = () => ({ maxHeight: "230px" });
  resizeComposerTextarea(element, styles);
  assert.equal(element.style.height, "96px");
  assert.equal(element.style.overflowY, "hidden");
  element.scrollHeight = 32;
  resizeComposerTextarea(element, styles);
  assert.equal(element.style.height, "32px");
});
test("long drafts scroll within the themed height limit", () => {
  const element = { style: {}, scrollHeight: 500 };
  resizeComposerTextarea(element, () => ({ maxHeight: "230px" }));
  assert.equal(element.style.height, "230px");
  assert.equal(element.style.overflowY, "auto");
});
test("an unlimited host theme and an unmounted field are supported", () => {
  const element = { style: {}, scrollHeight: 500 };
  resizeComposerTextarea(element, () => ({ maxHeight: "none" }));
  assert.equal(element.style.height, "500px");
  assert.doesNotThrow(() => resizeComposerTextarea(null));
});
test("sizing measures content once before writing the final height", () => {
  let measurements = 0;
  const element = { style: {}, get scrollHeight() { measurements++; return 500; } };
  resizeComposerTextarea(element, () => ({ maxHeight: "230px" }));
  assert.equal(measurements, 1);
  assert.equal(element.style.height, "230px");
  assert.equal(element.style.overflowY, "auto");
});
