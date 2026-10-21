import test from "node:test";
import assert from "node:assert/strict";
import { initialServer, restartPending, restoreServer, serverLifecycle } from "../../src/server-lifecycle.js";

const status = (id, phase = "ready") => ({ server: { instance_id: id, phase } });
const restarting = () => serverLifecycle(initialServer, { type: "server_restarting", instance_id: "old" });

test("a new healthy instance, not a reconnect to the old one, confirms restart", () => {
  const state = restarting();
  assert.ok(restartPending(state));
  assert.equal(serverLifecycle(state, status("old")), state);
  assert.equal(serverLifecycle(state, status("new", "restarting")), state);
  assert.equal(serverLifecycle(state, status("new")).phase, "restarted");
  assert.equal(serverLifecycle(initialServer, status("new")).phase, "idle");
});

test("failure remains explicit and cannot become success on the same server", () => {
  const state = serverLifecycle(restarting(), { type: "server_restart_failed", instance_id: "old", error: "no supervisor" });
  assert.equal(state.phase, "failed");
  assert.equal(serverLifecycle(state, status("old")).phase, "failed");
});

test("a pending restart survives reload but malformed storage is ignored", () => {
  const state = restarting();
  assert.deepEqual(restoreServer({getItem: () => JSON.stringify(state)}, "key"), state);
  for (const value of ["{", "null", "{}", '{"phase":"restarting"}'])
    assert.equal(restoreServer({getItem: () => value}, "key"), initialServer);
  assert.equal(restoreServer({getItem: () => { throw Error("disabled"); }}, "key"), initialServer);
});
