export function pluginStatusKey(plugin) {
  if (!plugin.running) return plugin.binding_available ? "stopped" : "serviceStopped";
  if (!plugin.binding_available) return "serviceActive";
  return plugin.binding_enabled ? "agentEnabled" : "agentDisabled";
}

export function pluginRunning(plugins, name) {
  return plugins.some((plugin) => plugin.name === name && plugin.running);
}
