import test from "node:test";
import assert from "node:assert/strict";
import { resizeComposerTextarea } from "../../src/composer-size.js";

test("sizing measures content once before writing the final height", () => {
  let measurements = 0;
  const element = { style: {}, get scrollHeight() { measurements++; return 500; } };
  resizeComposerTextarea(element, () => ({ maxHeight: "230px" }));
  assert.equal(measurements, 1);
  assert.equal(element.style.height, "230px");
  assert.equal(element.style.overflowY, "auto");
});
