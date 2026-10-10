import test from "node:test";
import assert from "node:assert/strict";

import { pluginRunning, pluginStatusKey } from "./plugins.js";

test("optional interface controls follow installed plugin runtimes", () => {
  assert.equal(pluginRunning([], "realtime"), false);
  assert.equal(pluginRunning([{ name: "realtime", running: false }], "realtime"), false);
  assert.equal(pluginRunning([{ name: "realtime", running: true }], "realtime"), true);
});


test("agent availability is distinct from service lifetime", () => {
  assert.equal(pluginStatusKey({ running: true, binding_available: true, binding_enabled: true }), "agentEnabled");
  assert.equal(pluginStatusKey({ running: true, binding_available: true, binding_enabled: false }), "agentDisabled");
  assert.equal(pluginStatusKey({ running: true, binding_available: false }), "serviceActive");
  assert.equal(pluginStatusKey({ running: false, binding_available: false }), "serviceStopped");
  assert.equal(pluginStatusKey({ running: false, binding_available: true, binding_enabled: true }), "stopped");
});
