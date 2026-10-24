"""Batch dictation is private, bounded and never creates a conversation turn."""

import asyncio
import io
import threading
from types import SimpleNamespace
from contextlib import contextmanager
import base64

import pytest
from starlette.datastructures import Headers, UploadFile
from starlette.testclient import TestClient
from the_framework.server.api.endpoints import HttpError
from the_harness.app import create_app
from the_harness.plugins.dictation import server as module


def upload(data=b"recording!", mime="audio/pcm"):
    return UploadFile(io.BytesIO(data), filename="untrusted-name", headers=Headers({"content-type": mime}))


def test_transcription_runs_off_loop_and_closes_upload(monkeypatch):
    main = threading.get_ident()
    calls = []
    def transcribe(audio, language, cancelled):
        assert threading.get_ident() != main
        calls.append((audio, language))
        return "Bonjour"
    monkeypatch.setattr(module, "transcribe_audio", transcribe)
    file = upload()
    assert asyncio.run(module.DictationService().transcribe([file], "fr")) == {"text": "Bonjour"}
    assert file.file.closed
    assert calls == [(b"recording!", "fr")]


@pytest.mark.parametrize("data,mime,status", [(b"", "audio/pcm", 422), (b"x", "text/plain", 415),
                                               (b"x" * 9, "audio/pcm", 413), (b"x", "audio/pcm", 422)])
def test_invalid_audio_is_rejected_and_closed(monkeypatch, data, mime, status):
    monkeypatch.setattr(module, "MAX_AUDIO_BYTES", 8)
    file = upload(data, mime)
    with pytest.raises(HttpError) as error:
        asyncio.run(module.DictationService().transcribe([file], "fr"))
    assert error.value.status_code == status
    assert file.file.closed


def test_errors_are_sanitized(monkeypatch):
    def broken(*args):
        raise RuntimeError("secret bearer token")
    monkeypatch.setattr(module, "transcribe_audio", broken)
    with pytest.raises(HttpError) as error:
        asyncio.run(module.DictationService().transcribe([upload()], "fr"))
    assert error.value.status_code == 502
    assert "secret" not in str(error.value)


@pytest.mark.parametrize("failure", [None, "error", "conversation.item.input_audio_transcription.failed"])
def test_sdk_uses_transcription_only_oauth_and_closes(monkeypatch, failure):
    calls, events = [], []
    class Connection:
        def send(self, event):
            events.append(event)
        def recv(self):
            if len(events) == 1:
                return {"type": "session.updated"}
            return {"type": failure or "conversation.item.input_audio_transcription.completed",
                    "transcript": " Bonjour ! "}
    class Client:
        def __init__(self, **kwargs):
            calls.append(kwargs)
            self.realtime = SimpleNamespace(connect=self.connect)
        def authenticate(self, **kwargs):
            calls.append(kwargs)
        @contextmanager
        def connect(self, **kwargs):
            calls.append(kwargs)
            try:
                yield Connection()
            finally:
                calls.append("socket closed")
        def close(self):
            calls.append("client closed")
    monkeypatch.setattr("codex_backend_sdk.OpenAI", Client)
    if failure:
        with pytest.raises(RuntimeError):
            module.transcribe_audio(b"test", "fr", threading.Event())
    else:
        assert module.transcribe_audio(b"test", "fr", threading.Event()) == "Bonjour !"
    assert calls == [{"timeout": 5, "max_retries": 0}, {"interactive": False},
                     {"intent": "transcription", "timeout": 5}, "socket closed", "client closed"]
    session = events[0]["session"]
    assert session["type"] == "transcription"
    assert session["audio"]["input"]["turn_detection"] is None
    assert session["audio"]["input"]["format"] == {"type": "audio/pcm", "rate": 24000}
    assert base64.b64decode(events[1]["audio"]) == b"test"
    assert events[2] == {"type": "input_audio_buffer.commit"}


def test_authenticated_routes_support_existing_mobile_pairing_and_reject_preview(tmp_path, monkeypatch):
    calls = []
    def transcribe(*args):
        calls.append(args)
        return "Bonjour"
    monkeypatch.setattr(module, "transcribe_audio", transcribe)
    app = create_app(session_path=tmp_path / "session.json", token="local", browser_token="browser",
                     browser_runtime_root=tmp_path, client_remote_root=tmp_path)
    with TestClient(app, base_url="http://127.0.0.1:48887") as client:
        url = "/api/v1/dictation/transcribe"
        def post(headers=None, **kwargs):
            return client.post(url, headers=headers, data={"language": "fr"},
                               files={"files": ("clip.webm", b"test", "audio/pcm")}, **kwargs)
        assert post().status_code in {401, 403}
        auth = {"Authorization": "Bearer local"}
        response = post(auth)
        assert response.status_code == 200, response.text
        assert response.json() == {"text": "Bonjour"}
        assert client.post(url, headers=auth, data={"language": "fr", "files": "not a file"}).status_code == 422
        assert client.post(url, headers=auth, data={"language": "xx"}, files={"files": ("x", b"x", "audio/pcm")}).status_code == 422
        assert client.post(url, headers=auth, data={"language": "fr"}, files=[("files", ("a", b"x")), ("files", ("b", b"x"))]).status_code == 422
        remote = app.state.application.default_session.extensions["client_remote_api"].service.service
        remote.network.endpoint = "https://computer.example.ts.net"
        device, token = remote.clients.issue("phone", platform="android")
        phone = {"Host": "computer.example.ts.net", "Origin": remote.network.endpoint,
                 "Cookie": "harness_mobile=" + token}
        assert post(phone).status_code == 200
        assert post({**phone, "Origin": "https://evil.example"}).status_code == 403
        remote.clients.revoke(device["id"])
        assert post(phone).status_code == 401
        # Preview credentials have only read scopes, never agent:write.
        from the_framework.server.api.endpoints import Principal
        from the_framework.server.clients.previews import authorize_preview
        assert not authorize_preview(Principal(id="surface-preview", scopes=frozenset({"*:read"})), {"scope": "agent:write"})
        assert len(calls) == 2


def test_disconnected_request_signals_worker_to_close(monkeypatch):
    closed = threading.Event()
    def transcribe(audio, language, cancelled):
        assert cancelled.wait(2), "disconnect must stop upstream work"
        closed.set()
    async def disconnected():
        return True
    monkeypatch.setattr(module, "transcribe_audio", transcribe)
    context = SimpleNamespace(request=SimpleNamespace(is_disconnected=disconnected))
    with pytest.raises(HttpError) as error:
        asyncio.run(module.DictationService().transcribe([upload()], "fr", context))
    assert error.value.status_code == 499
    assert closed.is_set()
