"""Private, bounded PCM dictation over an OAuth transcription-only socket."""

import asyncio
import base64
import threading
import time

from starlette.datastructures import UploadFile
from the_framework.server import endpoint
from the_framework.server.api.endpoints import HttpError

SAMPLE_RATE = 24_000
MAX_AUDIO_BYTES = SAMPLE_RATE * 2 * 120


def transcribe_audio(audio, language, cancelled):
    from codex_backend_sdk import OpenAI
    from websocket import WebSocketTimeoutException

    client = OpenAI(timeout=5, max_retries=0)
    deadline = time.monotonic() + 60

    def receive(connection, expected):
        while not cancelled.is_set() and time.monotonic() < deadline:
            try:
                event = connection.recv()
            except WebSocketTimeoutException:
                continue
            kind = event.get("type", "")
            if kind == "error" or kind.endswith(".failed"):
                raise RuntimeError("Upstream transcription failed")
            if kind == expected:
                return event
        raise TimeoutError("Transcription cancelled or timed out")

    try:
        client.authenticate(interactive=False)
        with client.realtime.connect(intent="transcription", timeout=5) as connection:
            connection.send({"type": "session.update", "session": {
                "type": "transcription", "audio": {"input": {
                    "format": {"type": "audio/pcm", "rate": SAMPLE_RATE},
                    "transcription": {"model": "gpt-4o-mini-transcribe", "language": language},
                    "turn_detection": None,
                }},
            }})
            receive(connection, "session.updated")
            for offset in range(0, len(audio), 24_000):
                if cancelled.is_set() or time.monotonic() >= deadline:
                    raise TimeoutError("Transcription cancelled or timed out")
                connection.send({"type": "input_audio_buffer.append", "audio":
                                 base64.b64encode(audio[offset:offset + 24_000]).decode("ascii")})
            connection.send({"type": "input_audio_buffer.commit"})
            return receive(connection, "conversation.item.input_audio_transcription.completed")["transcript"].strip()
    finally:
        client.close()


class DictationService:
    @endpoint("post", "/api/v1/dictation/transcribe", request_encoding="multipart",
              request={"type": "object", "properties": {
                  "files": {"type": "array", "minItems": 1, "maxItems": 1},
                  "language": {"type": "string", "enum": ["fr", "en"]},
              }, "required": ["files", "language"], "additionalProperties": False},
              response={"type": "object", "properties": {"text": {"type": "string"}},
                        "required": ["text"], "additionalProperties": False},
              authorization={"scope": "agent:write"}, context="context")
    async def transcribe(self, files, language, context=None):
        upload = files[0]
        if not isinstance(upload, UploadFile):
            raise HttpError(422, "invalid_audio", "Un fichier audio est nécessaire.")
        try:
            mime = (upload.content_type or "").split(";", 1)[0].lower()
            if mime != "audio/pcm":
                raise HttpError(415, "invalid_audio_type", "Format audio non pris en charge.")
            audio = await upload.read(MAX_AUDIO_BYTES + 1)
            if not audio:
                raise HttpError(422, "empty_audio", "L’enregistrement est vide.")
            if len(audio) > MAX_AUDIO_BYTES:
                raise HttpError(413, "audio_too_large", "L’enregistrement dépasse deux minutes.")
            if len(audio) % 2:
                raise HttpError(422, "invalid_pcm", "Audio PCM16 invalide.")
        finally:
            await upload.close()
        cancelled = threading.Event()
        worker = asyncio.create_task(asyncio.to_thread(transcribe_audio, audio, language, cancelled))
        try:
            while not worker.done():
                done, _ = await asyncio.wait({worker}, timeout=0.25)
                if not done and context and await context.request.is_disconnected():
                    raise HttpError(499, "dictation_cancelled", "Dictée annulée.")
            text = await worker
        except HttpError:
            raise
        except Exception as error:
            # Backend exceptions can contain account details: never return them.
            raise HttpError(502, "dictation_failed", "La transcription a échoué. Réessayez.") from error
        finally:
            cancelled.set()
            worker.cancel()
        return {"text": text}


def build_service(context):
    return DictationService()
