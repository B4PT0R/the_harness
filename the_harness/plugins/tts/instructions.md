# Local speech synthesis

Use `tts.synthesize` for explicitly requested speech with the configured local
Piper voice. Pass the exact words to read, not directions or a prompt.
Two independent switches control delivery:
- `show_artifact=true` (default): present a durable manual audio player. Do not
  publish the same result again. Artifacts themselves never autoplay.
- `play_audio=false` (default): set true only when immediate speech is wanted.
  Direct playback has no widget and targets only the last authenticated client
  that submitted an accepted message or explicitly started voice. Automatic
  reconnects and voice recovery do not select a client. Never broadcast or fall
  back to another device. If unavailable or blocked, report it without retrying.
Both false creates only a private WAV; both true displays and requests playback.
A `playing` receipt means playback started, not completed or heard.

Piper runs locally on CPU in a separate process. Installation and voice downloads
are separate setup steps in docs/tts.md, never automatic fallbacks. Missing runtime
or model is an error, not permission to send text remotely. This is separate from
Realtime voice. Do not infer human receipt from generated audio or an artifact.

For an explicitly authorized spoken native alarm, use `prepare_alarm_audio(text)`
to synthesize and publish exact words silently. It returns `audio_src`; pass that
reference to `scheduler.create_wake(delivery="alarm", audio_src=...)` or native
`create_wait`'s `alert.audio_src` with `kind="alarm"`. Preparation does not play,
display or schedule anything. The paired Android 0.1.7+ phone must sync/cache
before the alarm; missing audio falls back to its ringtone. No immediate-delivery
guarantee in deep sleep. Never test audible alarms without consent.
