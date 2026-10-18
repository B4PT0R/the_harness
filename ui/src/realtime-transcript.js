const record = (value) => value && typeof value === "object" && !Array.isArray(value) ? value : {};

// Completed captions stay visible until their canonical message arrives.
export class RemoteRealtimeTranscriptAssembler {
  active = {};
  ingest(value) {
    const outer = record(value);
    const payload = record(outer.payload);
    const envelope = payload.type === "realtime_event" ? payload : outer;
    if (envelope.type !== "realtime_event") return null;
    const event = record(envelope.event);
    const { role } = event;
    if (!["user", "assistant"].includes(role)) return null;
    if (event.type === "voice.turn.completed") {
      delete this.active[role];
      return { role, final: true, ...(event.message_id && event.transcript ? {
        message: { id: event.message_id, role, kind: "realtime",
          text: event.transcript, final: true, pending: true },
      } : {}) };
    }
    if (event.type !== "voice.transcript.updated" || typeof event.text !== "string" || !event.text || this.active[role] === event.text) return null;
    this.active[role] = event.text;
    return { role, completeText: event.text, final: false };
  }

  reset() { this.active = {}; }
}
