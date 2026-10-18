"""The paired-client API reuses chat ingress and preserves its wire contract."""

import asyncio
from types import SimpleNamespace

import pytest
from the_framework import Application
from the_framework.agent.runtime.protocol import SessionPageRequest, StatusRequest
from the_framework.plugins.realtime.api import RealtimeApi
from the_framework.server.api.chat import ChatApi
from the_framework.server.api.endpoints import HttpError, Principal
from the_framework.server.clients.remote import ClientRemoteService
from the_framework.server.runtime.supervisor import WorkerSupervisor

from the_harness.plugins.client_remote.api import ClientRemoteApi


def client_call():
    return SimpleNamespace(principal=Principal(
        id="remote:phone", attributes={"client": {"id": "phone"}},
    ))


@pytest.mark.parametrize("with_voice", [False, True])
def test_application_injects_the_installed_chat_ingress(tmp_path, monkeypatch, with_voice):
    from the_harness import app as server

    if not with_voice:
        monkeypatch.setattr(server, "application", Application({
            **server.application,
            "plugins": tuple(plugin for plugin in server.application.plugins if plugin.name != "realtime"),
        }))
    app = server.create_app(
        WorkerSupervisor(tmp_path / "session.json"), token="local", browser_token="browser",
        browser_runtime_root=tmp_path, client_remote_root=tmp_path,
    )
    assert "chat" not in app.state.application.plugins
    services = app.state.application.extensions
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
        api = ClientRemoteApi(service, chat.ingress)
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
        replay = ClientRemoteApi(restored, chat.ingress)
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
        api = ClientRemoteApi(service, ChatApi(runtime, tmp_path, voice).ingress)
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

        runtime = SimpleNamespace(request=request, bridge=SimpleNamespace(connected=False))
        service = ClientRemoteService(runtime, tmp_path / "clients.json")
        api = ClientRemoteApi(service, None)
        assert await api.state(client_call()) == {} and requested == []
        with pytest.raises(HttpError):
            await api.state(SimpleNamespace(principal=Principal(id="local")))
        result = await api.bootstrap(client_call(), limit=12)
        assert result["assistant"] == {} and result["session"] == {"turns": [], "before": "cursor"}
        assert len(requested) == 2
        assert result["event_cursor"] == 0 and result["server_instance_id"] == service.instance_id

    asyncio.run(run())


@pytest.mark.parametrize("contribution_first", [False, True])
def test_remote_policy_collects_all_features_before_accepting_clients(tmp_path, monkeypatch, contribution_first):
    from starlette.testclient import TestClient
    from the_framework import Plugin
    from the_framework.server.clients.remote import RemoteClientPolicy

    from the_harness import app as server
    from the_harness.plugins.client_remote.contributions import DESKTOP_ACCESS, POLICY

    def declare(context):
        context.contribute(POLICY, RemoteClientPolicy(
            capabilities=frozenset({"weather"}), platform_scopes={"quest": ("weather",)},
        ))
        context.contribute(DESKTOP_ACCESS, lambda access: access.add_exact(("GET", "/api/v1/weather")))
        return ()

    feature = Plugin(name="weather", server_extension=declare)
    plugins = server.application.plugins
    monkeypatch.setattr(server, "application", Application({
        **server.application,
        "plugins": (feature, *plugins) if contribution_first else (*plugins, feature),
    }))
    app = server.create_app(
        session_path=tmp_path / 'session.json', token='local', browser_token='browser',
        browser_runtime_root=tmp_path, client_remote_root=tmp_path,
        advertised_remote_endpoint='https://harness.example/',
    )
    with TestClient(app, base_url="http://127.0.0.1:48887") as client:
        service = app.state.application.services['client_remote']
        assert service.policy.capabilities == {'conversation', 'notifications', 'weather'}
        assert service.policy.scopes_for('quest') == ('chat', 'weather')
        assert service.desktop_api_allowed('GET', '/api/v1/weather')
        assert service.desktop_api_allowed('GET', '/api/v1/notifications/desktop')
        assert not service.desktop_api_allowed('POST', '/api/v1/weather')
        assert not service.desktop_api_allowed('GET', '/api/v1/local-files/open')
        with pytest.raises(RuntimeError, match='fixed'):
            service.desktop_access.add_exact(('POST', '/api/v1/weather'))
        headers = {'Authorization': 'Bearer local'}
        response = client.get('/api/v1/client-remote', headers=headers)
        assert response.status_code == 200, response.text
        status = response.json()
        assert status['suggested_endpoint'] == 'https://harness.example'
        pairing = client.post('/api/v1/client-remote/pairings', headers=headers, json={}).json()
        assert pairing['endpoint'] == 'https://harness.example'
