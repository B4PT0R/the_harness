// All application-owned UI copy, including accessible labels and error fallbacks.
// Backend errors, model output and user content retain their original language.
export const languages = { fr: "Français", en: "English" };
export const messages = {
  fr: {
    settings_general: "Général", settings_conversation: "Conversation", settings_capabilities: "Capacités",
    settings_interface: "Interface", settings_advanced: "Avancé", settings_data: "Données",
    settingsSections: "Sections des réglages", backToConversation: "Retour à la conversation",
    languageImmediate: "La langue de l’interface est appliquée immédiatement.",
    settingsSaved: "Réglages enregistrés.", unsavedSettings: "Modifications non enregistrées.",
    invalidConfig: "La configuration doit être un objet JSON valide.",
    invalidResponse: "Réponse du serveur invalide", agentEnabled: "Accessible", agentDisabled: "Masqué",
    requiredPlugin: "Capacité nécessaire au fonctionnement de l’agente",
    capabilitiesHelp: "Les cases contrôlent l’accès de l’agente aux outils et au contexte. Les services restent actifs ; les prérequis externes et vos autorisations restent nécessaires.",
    interfaceReleases: "Versions de l’interface", surfaceHelp: "Construire un aperçu ne change pas l’interface active. Vérifiez-le avant de publier. Vous pouvez annuler une compilation ; fermer les réglages ne l’arrête pas.",
    refresh: "Actualiser", noSurfaces: "Aucune interface déclarée", none: "Aucune",
    release_active: "Active", release_candidate: "Aperçu", release_previous: "Précédente",
    buildPreview: "Construire un aperçu", openPreview: "Ouvrir l’aperçu ↗", publish: "Publier", rollback: "Revenir en arrière", confirm: "Confirmer",
    publishWarning: "Publier cet aperçu et actualiser les interfaces connectées ? Vérifiez d’abord le rendu. La conversation est conservée ; les brouillons non envoyés peuvent être perdus.",
    rollbackWarning: "Restaurer la version précédente et actualiser les interfaces connectées ? La conversation est conservée ; les brouillons non envoyés peuvent être perdus.",
    buildingPreview: "Compilation de l’aperçu…", cancelBuild: "Annuler la compilation", buildCancelled: "Compilation annulée.",
    buildDone: "Aperçu prêt. Vérifiez-le avant publication.", publishDone: "Interface publiée.", rollbackDone: "Version précédente restaurée.",
    contextUsage: "Contexte : {percent} % ({tokens} / {limit} tokens estimés)", contextUnknown: "Occupation du contexte indisponible",
    compactContext: "Compacter le contexte", compactionQueued: "Compaction en attente…", compacting: "Compaction du contexte en cours…", compactionDone: "Contexte compacté.", compactionFailed: "La compaction a été interrompue ou a échoué.", workerDisconnected: "Le worker s’est déconnecté.",
    dangerZone: "Zone de danger", resetSession: "Réinitialiser la session", resetMemory: "Réinitialiser la mémoire",
    resetSessionWarning: "Effacer définitivement la conversation et son historique ? La mémoire, les fichiers et les réglages sont conservés. Toute activité en cours sera interrompue.",
    resetMemoryWarning: "Effacer définitivement la mémoire durable de l’agente ? La conversation, le registre, les fichiers et les réglages sont conservés. Toute activité en cours sera interrompue.",
    confirmReset: "Réinitialiser", resetting: "Réinitialisation…", resetDone: "Réinitialisation effectuée.",
    settings: "Réglages", close: "Fermer", language: "Langue", conversation: "Conversation",
    model: "Modèle", personalInstructions: "Instructions personnelles", optional: "Optionnel",
    capabilities: "Capacités", enablePlugin: "Activer {name} pour l’agent",
    loaded: "Chargé", stopped: "Arrêté", serviceActive: "Service actif", serviceStopped: "Service arrêté",
    advancedConfig: "Configuration avancée", configJson: "Configuration de l’agent en JSON",
    save: "Enregistrer", saving: "Enregistrement…", loading: "Chargement…", previousMessages: "Messages précédents",
    you: "Toi", assistant: "Assistant", live: "En direct", message: "Message", messagePlaceholder: "Message…",
    chatUnavailable: "Chat indisponible", working: "En cours…", removeAttachment: "Retirer {name}",
    attach: "Joindre un fichier", voiceStart: "Démarrer la voix", cancel: "Annuler", voiceStopping: "Arrêt de la voix…",
    voiceEnd: "Terminer la voix", stop: "Arrêter", send: "Envoyer", Connected: "Connecté", Connecting: "Connexion…", Reconnecting: "Reconnexion…",
    requestFailed: "Échec de la requête ({status})", voiceCancelled: "Connexion vocale annulée",
    voiceTimeout: "Délai de connexion audio dépassé", voiceFailed: "Échec de la connexion audio", voiceOfferFailed: "Impossible de préparer la connexion audio",
    plugin_memory: "Mémoire", plugin_realtime: "Voix", plugin_desktop_notifications: "Notifications", plugin_client_remote: "Clients distants",
    plugin_hosted_ui: "Interface", plugin_chat: "Chat", plugin_bash: "Terminal", plugin_web_search: "Recherche web",
    plugin_scheduler: "Planification", plugin_chromium: "Navigateur", plugin_system: "Système", plugin_registry: "Registre",
  },
  en: {
    settings_general: "General", settings_conversation: "Conversation", settings_capabilities: "Capabilities",
    settings_interface: "Interface", settings_advanced: "Advanced", settings_data: "Data",
    settingsSections: "Settings sections", backToConversation: "Back to conversation",
    languageImmediate: "The interface language is applied immediately.",
    settingsSaved: "Settings saved.", unsavedSettings: "Unsaved changes.",
    invalidConfig: "Configuration must be a valid JSON object.",
    invalidResponse: "Invalid server response", agentEnabled: "Available", agentDisabled: "Hidden",
    requiredPlugin: "Required for the agent to operate",
    capabilitiesHelp: "Checkboxes control the agent’s access to tools and context. Services stay active; external prerequisites and your authorization are still required.",
    interfaceReleases: "Interface versions", surfaceHelp: "Building a preview does not change the active interface. Check it before publishing. You can cancel a build; closing settings does not stop it.",
    refresh: "Refresh", noSurfaces: "No interfaces declared", none: "None",
    release_active: "Active", release_candidate: "Preview", release_previous: "Previous",
    buildPreview: "Build a preview", openPreview: "Open preview ↗", publish: "Publish", rollback: "Roll back", confirm: "Confirm",
    publishWarning: "Publish this preview and refresh connected interfaces? Check its appearance first. The conversation is preserved; unsent drafts may be lost.",
    rollbackWarning: "Restore the previous version and refresh connected interfaces? The conversation is preserved; unsent drafts may be lost.",
    buildingPreview: "Building preview…", cancelBuild: "Cancel build", buildCancelled: "Build cancelled.",
    buildDone: "Preview ready. Check it before publishing.", publishDone: "Interface published.", rollbackDone: "Previous version restored.",
    contextUsage: "Context: {percent}% ({tokens} / {limit} estimated tokens)", contextUnknown: "Context usage unavailable",
    compactContext: "Compact context", compactionQueued: "Compaction queued…", compacting: "Compacting context…", compactionDone: "Context compacted.", compactionFailed: "Compaction was interrupted or failed.", workerDisconnected: "The worker disconnected.",
    dangerZone: "Danger zone", resetSession: "Reset session", resetMemory: "Reset memory",
    resetSessionWarning: "Permanently erase the conversation and its history? Memory, files and settings are preserved. Any ongoing activity will be interrupted.",
    resetMemoryWarning: "Permanently erase the agent’s durable memory? The conversation, registry, files and settings are preserved. Any ongoing activity will be interrupted.",
    confirmReset: "Reset", resetting: "Resetting…", resetDone: "Reset complete.",
    settings: "Settings", close: "Close", language: "Language", conversation: "Conversation",
    model: "Model", personalInstructions: "Personal instructions", optional: "Optional",
    capabilities: "Capabilities", enablePlugin: "Enable {name} for the agent",
    loaded: "Loaded", stopped: "Stopped", serviceActive: "Service active", serviceStopped: "Service stopped",
    advancedConfig: "Advanced configuration", configJson: "Agent configuration JSON",
    save: "Save", saving: "Saving…", loading: "Loading…", previousMessages: "Previous messages",
    you: "You", assistant: "Assistant", live: "Live", message: "Message", messagePlaceholder: "Message…",
    chatUnavailable: "Chat unavailable", working: "Working…", removeAttachment: "Remove {name}",
    attach: "Attach a file", voiceStart: "Start voice", cancel: "Cancel", voiceStopping: "Stopping voice…",
    voiceEnd: "End voice", stop: "Stop", send: "Send", Connected: "Connected", Connecting: "Connecting…", Reconnecting: "Reconnecting…",
    requestFailed: "Request failed ({status})", voiceCancelled: "Voice connection cancelled",
    voiceTimeout: "Audio connection timed out", voiceFailed: "Audio connection failed", voiceOfferFailed: "Unable to prepare audio connection",
    plugin_memory: "Memory", plugin_realtime: "Voice", plugin_desktop_notifications: "Notifications", plugin_client_remote: "Remote clients",
    plugin_hosted_ui: "Interface", plugin_chat: "Chat", plugin_bash: "Terminal", plugin_web_search: "Web search",
    plugin_scheduler: "Scheduling", plugin_chromium: "Browser", plugin_system: "System", plugin_registry: "Registry",
  },
};
export const localeKey = "the-harness.locale";
export function resolveLocale(value) {
  const locale = String(value || "").toLowerCase().split(/[-_]/)[0];
  return Object.hasOwn(messages, locale) ? locale : "en";
}
export function readLocale() {
  try {
    return resolveLocale(globalThis.localStorage?.getItem(localeKey) || globalThis.navigator?.language);
  } catch { return resolveLocale(globalThis.navigator?.language); }
}
export function translate(key, values = {}, locale = readLocale()) {
  const text = messages[resolveLocale(locale)][key] ?? messages.en[key] ?? key;
  return text.replace(/\{(\w+)\}/g, (_, name) => String(values[name] ?? `{${name}}`));
}
