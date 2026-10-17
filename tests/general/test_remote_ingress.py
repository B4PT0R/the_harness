"""The paired-client API reuses chat ingress and preserves its wire contract."""

import asyncio
from types import SimpleNamespace

import pytest

from the_framework import ApplicationSpec
from the_framework.agent.runtime.protocol import SessionPageRequest, StatusRequest
from the_framework.server.api.chat import ChatApi
from the_framework.plugins.realtime.api import RealtimeApi
from the_framework.server.api.endpoints import HttpError, Principal
from the_framework.server.clients.remote import ClientRemoteService
from the_framework.server.runtime.supervisor import WorkerSupervisor
from the_harness.plugins.client_remote.composition import build_api
from the_harness.plugins.client_remote.policy import RemoteProjection


def client_call():
    return SimpleNamespace(principal=Principal(
        id="remote:phone", attributes={"client": {"id": "phone"}},
    ))


@pytest.mark.parametrize("with_voice", [False, True])
def test_application_injects_the_installed_chat_ingress(tmp_path, monkeypatch, with_voice):
    from the_harness import app as server

    if not with_voice:
        monkeypatch.setattr(server, "application", ApplicationSpec({
            **server.application,
            "plugins": tuple(plugin for plugin in server.application.plugins if plugin.name != "realtime"),
        }))
    app = server.create_app(
        WorkerSupervisor(tmp_path / "session.json"), token="local", browser_token="browser",
        browser_runtime_root=tmp_path, client_remote_root=tmp_path,
    )
    assert "chat" not in app.state.application.plugins
    services = app.state.application.server_extensions
    chat = services["chat"].service
    remote = services["client_remote_api"].service
    assert remote.ingress is chat.ingress
    assert remote.runtime is chat.runtime
    assert remote.ingress.lock is (services["realtime"].service.lock if with_voice else chat.ingress.lock)
    assert (remote.ingress.voice is not None) == with_voice
    assert services["client_remote_api"].requires_services == ("client_remote", "chat")


@pytest.mark.parametrize("active_voice", [False, True])
def test_remote_prompts_keep_ids_routes_and_persistent_receipts(tmp_path, active_voice):
    async def run():
        submitted, spoken = [], []

        async def submit(command):
            submitted.append(command)

        async def send_text(text):
            spoken.append(text)
            return "voice-turn"

        runtime = SimpleNamespace(submit=submit)
        voice = RealtimeApi(runtime, SimpleNamespace(active=active_voice, send_text=send_text))
        chat = ChatApi(runtime, tmp_path, voice)
        service = ClientRemoteService(runtime, tmp_path / "clients.json")
        api = build_api(runtime, service, chat.ingress, RemoteProjection())
        async with voice.lock:
            pending = asyncio.create_task(api.prompt(client_call(), "Hello", command_id="one"))
            await asyncio.sleep(0)
            assert not pending.done() and submitted == spoken == []
        result = await pending
        assert result == {
            "id": "voice-turn" if active_voice else "one", "command_id": "one",
            "status": "submitted", "route": "realtime" if active_voice else "text",
        }
        # A receipt survives a changed modality and a service reconstruction.
        voice.controller.active = not active_voice
        restored = ClientRemoteService(runtime, tmp_path / "clients.json")
        replay = build_api(runtime, restored, chat.ingress, RemoteProjection())
        assert await replay.prompt(client_call(), "Hello", id="one") == {**result, "deduplicated": True}
        with pytest.raises(HttpError) as conflict:
            await replay.prompt(client_call(), "Different", id="one")
        assert conflict.value.status_code == 409
        assert len(submitted) + len(spoken) == 1
        if submitted:
            assert submitted[0].id == "one" and submitted[0].append_prompt
        with pytest.raises(HttpError) as blank:
            await api.prompt(client_call(), " ", id="blank")
        assert blank.value.status_code == 422

    asyncio.run(asyncio.wait_for(run(), 5))


def test_failed_voice_submission_is_retryable_and_text_only_turns_are_preserved(tmp_path):
    async def run():
        submitted = []

        async def submit(command):
            submitted.append(command)

        async def send_text(text):
            if not controller.ready:
                raise RuntimeError("not ready")
            return "voice-turn"

        runtime = SimpleNamespace(submit=submit)
        controller = SimpleNamespace(active=True, ready=False, send_text=send_text)
        voice = RealtimeApi(runtime, controller)
        service = ClientRemoteService(runtime, tmp_path / "clients.json")
        api = build_api(runtime, service, ChatApi(runtime, tmp_path, voice).ingress, RemoteProjection())
        with pytest.raises(HttpError) as failure:
            await api.prompt(client_call(), "Hello", id="retry")
        assert failure.value.status_code == 409 and not service.command_receipts
        controller.ready = True
        assert (await api.prompt(client_call(), "Hello", id="retry"))["route"] == "realtime"
        with pytest.raises(HttpError):
            await api.prompt(client_call(), "", id="text-only", append_prompt=False)
        assert ("phone", "text-only") not in service.command_receipts
        controller.active = False
        assert (await api.prompt(client_call(), "", id="text-only", append_prompt=False))["route"] == "text"
        assert not submitted[0].append_prompt

    asyncio.run(run())


def test_empty_assistant_projection_needs_no_worker_snapshots(tmp_path):
    async def run():
        requested = []

        async def request(command, **kwargs):
            requested.append(command)
            if isinstance(command, StatusRequest):
                return {"foreground_pending": 0}
            assert isinstance(command, SessionPageRequest)
            assert command.projection == "remote" and command.limit == 12
            return {"turns": [], "before": "cursor"}

        runtime = SimpleNamespace(request=request, application=SimpleNamespace(connected=False))
        service = ClientRemoteService(runtime, tmp_path / "clients.json")
        api = build_api(runtime, service, None, RemoteProjection())
        assert await api.state(client_call()) == {} and requested == []
        with pytest.raises(HttpError):
            await api.state(SimpleNamespace(principal=Principal(id="local")))
        result = await api.bootstrap(client_call(), limit=12)
        assert result["assistant"] == {} and result["session"] == {"turns": [], "before": "cursor"}
        assert len(requested) == 2
        assert result["event_cursor"] == 0 and result["server_instance_id"] == service.instance_id

    asyncio.run(run())
