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
