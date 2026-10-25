# Local text-to-speech

The optional `tts` plugin reads text with Piper on CPU. It runs in a separate
Python 3.12 process: no Piper, ONNX Runtime or NumPy imports in the agent worker,
no persistent synthesis server and no GPU dependency. Synthesis is local;
installation and voice downloads are separate, explicit setup steps.

## Setup

From the repository root:

```sh
uv sync --project the_harness/plugins/tts/runtime --frozen
the_harness/plugins/tts/runtime/.venv/bin/python -m piper.download_voices \
  --data-dir "$HOME/.local/share/piper/voices" fr_FR-siwis-medium
```

The default voice is `~/.local/share/piper/voices/fr_FR-siwis-medium.onnx`, alongside
its `.onnx.json` configuration. Keep its upstream MODEL_CARD with the voice:
https://huggingface.co/rhasspy/piper-voices/blob/main/fr/fr_FR/siwis/medium/MODEL_CARD
The card attributes the SIWIS dataset under CC-BY 4.0. Piper itself is GPL-3.0;
check each voice's licensing before redistributing it. Dependencies and voices
are downloaded locally, not vendored into this repository.

On the development machine the initial runtime occupies about 170 MiB and the
single French voice about 61 MiB (filesystem usage, not a portable guarantee).
Restart the server after installing the plugin; its agent binding can then be
enabled or disabled like other optional tools.

## Tool and configuration

`tts.synthesize(text, show_artifact=True, play_audio=False)` accepts 1–4000
characters and generates a mono PCM16 WAV. It returns the private path, duration
and sample rate. Delivery switches are independent:

| show_artifact | play_audio | Result |
| --- | --- | --- |
| true | false | Durable manual player (default) |
| false | true | Direct playback, no widget |
| true | true | Player plus direct playback |
| false | false | Private WAV only |

The active target is the authenticated per-page client of the last accepted human
message (including attachments) or successful explicit voice start. Server
acceptance order decides; failed inputs, opening/focusing a page, reconnecting,
and automatic voice recovery do not take over. A client without an identifiable
page clears the target rather than selecting a default desktop. Identity is scoped
to the authenticated principal; a page UUID is not a credential or proof of presence.
This is a participation signal, not a claim to know the user's physical location.

Direct operations are transient and acknowledged over that client's authenticated
socket, never broadcast, queued offline, replayed from history, or rerouted to
another device. Handoff requests stopping the previous client's direct audio;
socket closure also stops it locally. The target resets on server restart or page
reload until another accepted input. Reconnection of the same page can restore
availability but never replays missed audio. Browser playback restrictions may
return `blocked`; disconnection/unavailability or missing acknowledgement are
reported without retry. `playing` means started, not heard or finished. The manual
artifact player never autoplays; direct playback requires `play_audio=True`.
This is separate from the Realtime voice, and does not schedule a reminder or
change notification behavior. Do not republish the same result with show_artifact.

The session configuration supports:

- `tts.model`: local ONNX path (the corresponding `.json` file is required).
- `tts.python`: optional alternative interpreter with Piper installed.
- `tts.timeout_seconds`: default 60, range 1–300.

Missing dependencies or models fail with setup instructions, without downloads
or a remote fallback during synthesis. Work is serialized per extension; timeout
or cancellation terminates the subprocess group and removes partial output.
Completed WAVs live under the private session's `tts/` directory. Publication
copies audio into the existing authenticated bucket, so the player survives
restarts independently of the source file. Published audio follows the same
access controls as existing file/image artifacts. Text passed to the tool is
part of the normal agent conversation; local synthesis does not make the model
conversation offline.

## Autoplay volume

Settings → Audio provides an immediate 0–100% volume control for direct TTS
playback (0% mutes). It is remembered in this browser/device, independently of
other devices, and also updates ongoing TTS playback. The default remains 100%.
It does not alter Realtime voice or manual artifact players.

## Audio artifacts

`artifacts.show_artifact(kind="audio", payload={"path": "/local/speech.wav",
"title": "Reminder", "description": "Optional transcript"})` presents an existing
file with browser playback controls and a download link. Common recognized audio
extensions such as WAV, MP3, OGG, FLAC and M4A are accepted; actual codec support
depends on the browser. A playback error keeps the download link available.
The player never autoplays or preloads the whole recording. An artifact does not
prove playback or that anyone heard its content.

## Verification

```sh
uv run pytest -q tests/general/test_tts_plugin.py
HARNESS_TTS_LIVE=1 uv run pytest -q -s tests/agentic/test_tts_live.py
```

The live test requires the installed runtime and default voice. It uses only a
synthetic reminder, validates WAV metadata and non-silent samples, and does not
play audio or open the microphone.

## Spoken native alarms

`tts.prepare_alarm_audio(text)` silently prepares a bucket resource for scheduled
Android alarms. Pass its `audio_src` to an explicitly authorized native alarm;
preparation alone neither displays a player, plays audio nor schedules anything.
The phone preloads it and plays offline. Limits: 180 seconds / 8 MiB per file.
See [alarm speech](alarm-speech.md) for synchronization, fallback and sleep limits.
