import test from "node:test";
import assert from "node:assert/strict";

import { pluginBindingEnabled, pluginStatusKey } from "../../src/plugins.js";

test("optional interface controls require a running service and an enabled binding", () => {
  assert.equal(pluginBindingEnabled([], "realtime"), false);
  assert.equal(pluginBindingEnabled([{ name: "realtime", running: false, binding_enabled: true }], "realtime"), false);
  assert.equal(pluginBindingEnabled([{ name: "realtime", running: true, binding_enabled: true }], "realtime"), true);
});

test("agent availability is distinct from service lifetime", () => {
  assert.equal(pluginStatusKey({ running: true, binding_available: true, binding_enabled: true }), "agentEnabled");
  assert.equal(pluginStatusKey({ running: true, binding_available: true, binding_enabled: false }), "agentDisabled");
  assert.equal(pluginStatusKey({ running: true, binding_available: false }), "serviceActive");
  assert.equal(pluginStatusKey({ running: false, binding_available: false }), "serviceStopped");
  assert.equal(pluginStatusKey({ running: false, binding_available: true, binding_enabled: true }), "stopped");
});

test("an installed voice runtime does not expose a disabled agent binding", () => {
  assert.equal(pluginBindingEnabled([
    { name: "realtime", running: true, binding_enabled: false },
  ], "realtime"), false);
});
