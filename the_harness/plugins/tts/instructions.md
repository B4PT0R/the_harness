# Local speech synthesis

Use `tts.synthesize` to read an explicitly requested text with the configured local
Piper voice. Pass the exact words to read, not directions or a conversational prompt.
The tool creates a WAV and automatically presents a durable audio player in the chat;
do not publish the result again. Playback is manual, never automatic.

Piper runs on CPU in a separate process; synthesis uses local files only. Installation
and voice downloads are separate setup steps documented in docs/tts.md, never automatic
fallbacks during synthesis. A missing runtime or model is an error, not permission to
send the text to a remote service. This voice is separate from Realtime voice.
A generated file or artifact is not proof that the user played or heard the audio.
