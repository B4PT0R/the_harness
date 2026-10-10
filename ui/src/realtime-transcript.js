const record = (value) => value && typeof value === "object" && !Array.isArray(value) ? value : {};

// Ephemeral captions only. Completed turns come from the canonical server session.
export class RemoteRealtimeTranscriptAssembler {
  active = {};

  ingest(value) {
    const outer = record(value);
    const payload = record(outer.payload);
    const envelope = payload.type === "realtime_event" ? payload : outer;
    if (envelope.type !== "realtime_event") return null;
    const event = record(envelope.event);
    if (event.type === "turn.done") {
      const { role } = record(event.turn);
      if (role !== "user" && role !== "assistant") return null;
      delete this.active[role];
      return { role, final: true };
    }
    const role = event.type === "input_transcript.added" ? "user"
      : event.type === "output_transcript.added" ? "assistant" : null;
    const { text } = record(event.item);
    if (!role || typeof text !== "string" || !text) return null;
    const current = this.active[role] ?? "";
    const delta = text.startsWith(current) ? text.slice(current.length)
      : current.endsWith(text) ? "" : text;
    if (!delta) return null;
    const completeText = current + delta;
    this.active[role] = completeText;
    return { role, completeText, final: false };
  }

  reset() { this.active = {}; }
}
