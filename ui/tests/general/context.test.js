import { test } from "node:test";
import assert from "node:assert/strict";
import { contextState, contextPercent, initialContext } from "../../src/context.js";
const event = (type, command_id = "turn") => ({ type: "command_event", command_id, event: { type } });
const status = (extra = {}) => ({ type: "worker_status", local_input_tokens: 50, context_token_limit: 200, ...extra });

test("context gauge uses local token count and clamps only its visual percentage", () => {
  const state = contextState(initialContext, status());
  assert.equal(state.ratio, 0.25);
  assert.equal(contextPercent(state.ratio), 25);
  assert.equal(contextPercent(1.2), 100);
  assert.equal(contextPercent(-1), 0);
  assert.equal(contextPercent(null), null);
  assert.equal(contextState(state, status({ context_token_limit: 0 })).ratio, null);
});
test("manual compaction goes through queued, running and complete", () => {
  let state = contextState(initialContext, { type: "command_accepted", command: { type: "compact_request", id: "compact" } });
  assert.equal(state.phase, "queued");
  state = contextState(state, event("agent.compaction.start", "compact"));
  assert.equal(state.phase, "running");
  state = contextState(state, event("agent.compaction.end", "compact"));
  assert.equal(state.phase, "done");
  state = contextState(state, status({ local_input_tokens: 12 }));
  assert.equal(state.tokens, 12);
  assert.equal(state.phase, "done");
});
test("automatic compaction is visible and failures clear its spinner", () => {
  let state = contextState(initialContext, event("agent.compaction.start"));
  assert.equal(state.phase, "running");
  assert.equal(contextState(state, { type: "command_failed", command: { type: "prompt_request", id: "other" } }), state);
  state = contextState(state, { type: "command_failed", command: { type: "prompt_request", id: "turn" } });
  assert.equal(state.phase, "failed");
  state = contextState(initialContext, event("agent.compaction.end"));
  assert.equal(contextState(state, event("agent.generation.start")).phase, "idle");
});
test("reconnect restores automatic and queued compaction from worker status", () => {
  const running = contextState(initialContext, status({ compaction_active: true, active: { type: "prompt_request", id: "turn" } }));
  assert.equal(running.phase, "running");
  assert.equal(running.commandId, "turn");
  assert.equal(contextState(initialContext, status({ compaction_pending: 1 })).phase, "queued");
  assert.equal(contextState(running, status()).phase, "idle");
  assert.equal(contextState(running, { type: "worker_exited" }).phase, "failed");
});


test("cache EMA comes from durable worker status, never recalculated on reconnect", () => {
  const cache_hit = { alpha: 0.1, ema_percent: 0, last_percent: null, samples: 3, unreported: 1 };
  const measured = contextState(initialContext, status({ cache_hit }));
  assert.equal(measured.cacheHit.ema_percent, 0);
  assert.equal(contextState(measured, status({ cache_hit })).cacheHit.samples, 3);
  assert.equal(contextState(measured, event("agent.generation.start")).cacheHit, cache_hit);
  assert.equal(contextState(measured, status()).cacheHit, null);
  assert.equal(contextState(measured, { type: "worker_exited" }).cacheHit, null);
});
