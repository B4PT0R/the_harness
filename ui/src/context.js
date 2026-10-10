// Display-only state. The worker remains the owner of context and compaction.
export const initialContext = { tokens: null, limit: null, ratio: null, phase: "idle", commandId: null };

export function contextState(current, output) {
  if (output.type === "worker_status") {
    const known = Number.isFinite(output.local_input_tokens) && output.context_token_limit > 0;
    let phase = current.phase;
    let commandId = current.commandId;
    if (output.compaction_active || output.active?.type === "compact_request") {
      phase = "running";
      commandId = output.active?.id ?? commandId;
    } else if (output.compaction_pending > 0) {
      phase = "queued";
    } else if (["queued", "running"].includes(phase)) {
      phase = "idle";
      commandId = null;
    }
    return { ...current, phase, commandId,
      tokens: known ? output.local_input_tokens : null,
      limit: known ? output.context_token_limit : null,
      ratio: known ? output.local_input_tokens / output.context_token_limit : null,
    };
  }
  if (output.type === "command_event") {
    if (output.event?.type === "agent.compaction.start")
      return { ...current, phase: "running", commandId: output.command_id };
    if (output.event?.type === "agent.compaction.end")
      return { ...current, phase: "done" };
    if (["agent.generation.start", "agent.turn.start"].includes(output.event?.type) && ["done", "failed"].includes(current.phase))
      return { ...current, phase: "idle", commandId: null };
  }
  if (output.type === "command_accepted" && output.command?.type === "compact_request")
    return current.phase === "running" ? current : { ...current, phase: "queued", commandId: output.command.id };
  if (output.type === "command_accepted" && output.command?.type === "prompt_request" && ["done", "failed"].includes(current.phase))
    return { ...current, phase: "idle", commandId: null };
  if (["command_completed", "command_failed"].includes(output.type) &&
      (output.command?.type === "compact_request" || output.command?.id === current.commandId))
    return { ...current, phase: output.type === "command_failed" ? "failed" : "done", commandId: null };
  if (["worker_exited", "worker_transport_error"].includes(output.type))
    return { ...initialContext, phase: ["queued", "running"].includes(current.phase) ? "failed" : "idle" };
  return current;
}

export function contextPercent(ratio) {
  return Number.isFinite(ratio) ? Math.round(Math.max(0, Math.min(1, ratio)) * 100) : null;
}
