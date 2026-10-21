// Server identity, not WebSocket connectivity, confirms a completed restart.
export const initialServer = { phase: "idle", instanceId: null };
export const restartPending = (state) => ["restarting", "waiting"].includes(state.phase);

export function serverLifecycle(current, output) {
  if (output.type === "server_restarting")
    return { phase: "restarting", instanceId: output.instance_id };
  if (output.type === "server_restart_failed")
    return { phase: "failed", instanceId: output.instance_id, error: output.error };
  const server = output.server;
  if (!server?.instance_id) return current;
  if (server.phase === "restarting")
    return restartPending(current) ? current : { phase: "restarting", instanceId: server.instance_id };
  if (restartPending(current))
    return server.instance_id !== current.instanceId && server.phase === "ready"
      ? { phase: "restarted", instanceId: server.instance_id } : current;
  return { ...current, instanceId: server.instance_id };
}

export function restoreServer(storage, key) {
  try {
    const saved = JSON.parse(storage.getItem(key));
    if (restartPending(saved || {}) && typeof saved.instanceId === "string") return saved;
  } catch { /* Disabled storage must not prevent reconnection. */ }
  return initialServer;
}
