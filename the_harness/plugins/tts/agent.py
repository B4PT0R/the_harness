import asyncio
import os
from pathlib import Path
import signal
from tempfile import TemporaryDirectory
from uuid import uuid4
import wave

from the_framework.agent import AgentExtension, Artifact, tool
from the_framework.agent.models.config import Config

RUNTIME = Path(__file__).parent / "runtime"
DEFAULT_MODEL = Path.home() / ".local/share/piper/voices/fr_FR-siwis-medium.onnx"


class TTSConfig(Config):
    python: str = ""
    model: str = str(DEFAULT_MODEL)
    timeout_seconds: int = 60


class TTSExtension(AgentExtension):
    name = "tts"
    description = "Local Piper text-to-speech and playable audio artifacts."
    instructions_file = "instructions.md"
    config = TTSConfig

    def load(self):
        if self.loaded:
            return self
        super().load()
        self._temporary = TemporaryDirectory(prefix="harness-tts-") if not self.agent.session_root else None
        self.root = self.agent.session_root / "tts" if self.agent.session_root else Path(self._temporary.name)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._lock = asyncio.Lock()
        return self

    def shutdown(self):
        if self._temporary is not None:
            self._temporary.cleanup()

    async def _synthesize(self, text, model, output):
        python = Path(self.config.python).expanduser() if self.config.python else RUNTIME / ".venv/bin/python"
        if not python.is_file():
            raise RuntimeError("Piper runtime missing. Run: uv sync --project the_harness/plugins/tts/runtime --frozen")
        with (output.parent / "piper.log").open("wb") as log:
            process = await asyncio.create_subprocess_exec(
                str(python), str(RUNTIME / "synthesize.py"), str(model), str(output),
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.DEVNULL, stderr=log,
                start_new_session=True,
                env={**os.environ, "OMP_NUM_THREADS": "2", "HF_HUB_OFFLINE": "1",
                     "HF_HUB_DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1"},
            )
            try:
                await asyncio.wait_for(process.communicate(text.encode("utf-8")), self.config.timeout_seconds)
            except (asyncio.CancelledError, TimeoutError):
                if process.returncode is None:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    await process.wait()
                raise
        if process.returncode:
            with (output.parent / "piper.log").open("rb") as log:
                log.seek(max(0, log.seek(0, 2) - 2000))
                detail = log.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Piper synthesis failed (exit {process.returncode}): {detail}")

    @tool
    async def synthesize(self, text: str, show_artifact: bool = True, play_audio: bool = False):
        """Synthesize 1–4000 characters locally; display and playback are independent.

        show_artifact presents a durable manual audio player (default true).
        play_audio requests immediate playback only on the last client that sent
        a message or started voice (default false). No broadcast or fallback.
        Both may be true or false. Returns the WAV path and playback receipt;
        playing means started, not heard or finished. Do not republish an artifact
        already returned here. Browser restrictions can block direct playback.
        """
        if not isinstance(show_artifact, bool) or not isinstance(play_audio, bool):
            raise ValueError("show_artifact and play_audio must be booleans.")
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 4000:
            raise ValueError("text must contain 1–4000 non-blank characters.")
        timeout = self.config.timeout_seconds
        if not isinstance(timeout, int) or isinstance(timeout, bool) or not 1 <= timeout <= 300:
            raise ValueError("tts.timeout_seconds must be an integer from 1 to 300.")
        model = Path(self.config.model).expanduser().resolve()
        if not model.is_file() or not Path(str(model) + ".json").is_file():
            raise FileNotFoundError("Piper voice missing (both .onnx and .onnx.json required). See docs/tts.md for setup.")
        async with self._lock:
            with TemporaryDirectory(prefix=".synthesize-", dir=self.root) as temporary:
                output = Path(temporary) / "speech.wav"
                await self._synthesize(text.strip(), model, output)
                with wave.open(str(output), "rb") as audio:
                    if not audio.getnframes() or audio.getsampwidth() != 2 or audio.getnchannels() != 1:
                        raise ValueError("Piper did not produce non-empty mono PCM16 audio.")
                    sample_rate = audio.getframerate()
                    duration = audio.getnframes() / sample_rate
                destination = self.root / f"{uuid4().hex}.wav"
                os.chmod(output, 0o600)
                output.rename(destination)
        result = {"path": str(destination), "duration_seconds": round(duration, 3),
                  "sample_rate": sample_rate, "voice": model.stem}
        if show_artifact or play_audio:
            payload = await self.agent.bridge.call(
                "artifacts", "publish", {
                    "kind": "audio", "payload": {"path": str(destination), "title": "Synthèse vocale", "description": text.strip()},
                }, timeout_ms=120_000)
            if play_audio:
                result["playback"] = await self.agent.bridge.call(
                    "tts", "play", {"src": payload["src"]}, timeout_ms=15_000)
            if show_artifact:
                return result, Artifact(kind="audio", payload=payload)
        return result

    @tool
    async def prepare_alarm_audio(self, text: str):
        """Prepare exact spoken words for a native alarm, without playing or displaying audio.

        Returns audio_src to pass to scheduler.create_wake (delivery=alarm) or
        create_wait's alert.audio_src (kind=alarm). The phone must sync and report
        audio_ready before offline speech is available. Otherwise the ringtone is
        the fallback. This does not schedule anything or prove human receipt.
        """
        result = await self.synthesize(text, show_artifact=False, play_audio=False)
        if result["duration_seconds"] > 180 or Path(result["path"]).stat().st_size > 8 * 1024 * 1024:
            raise ValueError("Alarm speech must fit within 180 seconds and 8 MiB; shorten the text.")
        payload = await self.agent.bridge.call("artifacts", "publish", {
            "kind": "audio", "payload": {"path": result["path"], "title": "Message d’alarme"},
        }, timeout_ms=120_000)
        return {**result, "audio_src": payload["src"]}
