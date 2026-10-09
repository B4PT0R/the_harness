import asyncio
from pathlib import Path

import pytest

from the_framework.agent import Agent, Image, ProviderOutput
from the_framework.server.clients.browser import (
    BROWSER_AGENT_ID_ATTR,
    BrowserError,
    BrowserService,
    BrowserSession,
)
from the_framework.server.clients.browser_rpc import BrowserRPCClient, BrowserRPCServer
from the_harness.plugins.browser import ChromiumExtension


class FakeKeyboard:
    def __init__(self):
        self.calls = []

    async def press(self, key):
        self.calls.append(key)


class FakeLocator:
    def __init__(self, selector):
        self.selector = selector
        self.calls = []

    async def click(self):
        self.calls.append(("click",))

    async def fill(self, text):
        self.calls.append(("fill", text))

    async def select_option(self, value):
        self.calls.append(("select", value))
        return [value]

    async def press(self, key):
        self.calls.append(("press", key))


class FakePage:
    def __init__(self, context):
        self.context = context
        self.url = "about:blank"
        self.keyboard = FakeKeyboard()
        self.goto_calls = []
        self.locators = []
        self.front = False

    async def evaluate(self, script, arg=None):
        if arg is None:
            return {"visibilityState": "visible", "hasFocus": self.front}
        return {
            "url": self.url,
            "title": "Fake page",
            "elements": [{"id": "1", "role": "button", "name": "Continue"}],
            "truncated": False,
        }

    async def goto(self, url, **kwargs):
        self.url = url
        self.goto_calls.append((url, kwargs))

    async def go_back(self, **kwargs):
        self.url = "about:blank"

    async def bring_to_front(self):
        for page in self.context.pages:
            page.front = False
        self.front = True

    async def title(self):
        return "Fake page"

    async def screenshot(self, path, full_page=False):
        Path(path).write_bytes(b"fake image")

    async def close(self):
        if self in self.context.pages:
            self.context.pages.remove(self)

    def locator(self, selector):
        locator = FakeLocator(selector)
        self.locators.append(locator)
        return locator


class FakeContext:
    async def add_cookies(self, cookies):
        self.cookies = cookies

    def __init__(self):
        self.pages = []
        self.closed = False
        self.listeners = {}
        self.routes = []

    def on(self, event, callback):
        # Match Playwright's wrapper cache on bound-method owners.
        owner = getattr(callback, "__self__", None)
        if owner is not None:
            setattr(owner, "_pw_impl_instance_" + callback.__name__, callback)
        self.listeners[event] = callback

    async def new_page(self):
        page = FakePage(self)
        self.pages.append(page)
        return page

    async def close(self):
        self.closed = True
        callback = self.listeners.get("close")
        if callback:
            callback()

    async def route(self, pattern, handler):
        self.routes.append((pattern, handler))


class FakeRoute:
    def __init__(self):
        self.action = None

    async def continue_(self):
        self.action = "continue"

    async def abort(self, reason):
        self.action = ("abort", reason)


class FakeRequest:
    def __init__(self, url):
        self.url = url


class FakeChromium:
    def __init__(self):
        self.context = FakeContext()
        self.launches = []

    async def launch_persistent_context(self, **kwargs):
        self.launches.append(kwargs)
        return self.context


class FakePlaywright:
    def __init__(self):
        self.chromium = FakeChromium()
        self.stopped = False

    async def stop(self):
        self.stopped = True


class FakeManager:
    def __init__(self):
        self.playwright = FakePlaywright()

    async def start(self):
        return self.playwright


class PlaywrightFactory:
    def __init__(self):
        self.managers = []

    def __call__(self):
        manager = FakeManager()
        self.managers.append(manager)
        return manager


def test_browser_service_uses_separate_persistent_profiles(tmp_path):
    asyncio.run(_browser_service_uses_separate_persistent_profiles(tmp_path))


def test_browser_authentication_is_installed_on_lazy_start_and_restart(tmp_path):
    async def check():
        factory = PlaywrightFactory()
        cookies = [{"name": "session", "value": "test", "url": "http://127.0.0.1:5173"}]
        service = BrowserService(tmp_path, playwright_factory=factory, initial_cookies=cookies)
        await service.open_application_ui("http://127.0.0.1:5173/ui/")
        assert not service.session("web").started
        assert service.session("harness_ui").context.cookies == cookies
        for _ in range(2):
            await service.open_web("http://127.0.0.1:5173/preview/")
            assert service.session("web").context.cookies == cookies
            await service.close_web()
        await service.stop()
    asyncio.run(check())


def test_browser_service_accepts_only_configured_remote_harness_origin(tmp_path):
    async def run():
        factory = PlaywrightFactory()
        service = BrowserService(
            tmp_path,
            playwright_factory=factory,
            application_ui_origins={"https://assistant.example"},
        )
        await service.open_application_ui("https://assistant.example/remote-ui/")
        launch = factory.managers[0].playwright.chromium.launches[0]
        assert launch["args"][0] == "--app=https://assistant.example/remote-ui/"
        assert "VaapiVideoDecoder" in launch["args"][2]
        with pytest.raises(BrowserError):
            await service.open_application_ui("https://other.example/remote-ui/")
        await service.stop()

    asyncio.run(run())


async def _browser_service_uses_separate_persistent_profiles(tmp_path):
    factory = PlaywrightFactory()
    cookies = [{"name": "session", "value": "test", "url": "http://127.0.0.1:5173"}]
    service = BrowserService(tmp_path, playwright_factory=factory, initial_cookies=cookies)

    await service.open_web("https://example.com")
    await service.open_application_ui("http://127.0.0.1:5173/dashboard/?token=secret#start")

    assert len(factory.managers) == 2
    web_launch = factory.managers[0].playwright.chromium.launches[0]
    ui_launch = factory.managers[1].playwright.chromium.launches[0]
    assert web_launch["user_data_dir"].endswith("browser/profiles/web")
    assert ui_launch["user_data_dir"].endswith("browser/profiles/harness_ui")
    assert web_launch["user_data_dir"] != ui_launch["user_data_dir"]
    assert web_launch["viewport"] == {"width": 1365, "height": 900}
    assert web_launch["no_viewport"] is False
    assert ui_launch["viewport"] is None
    assert ui_launch["no_viewport"] is True
    assert ui_launch["args"] == [
        "--app=http://127.0.0.1:5173/dashboard/",
        "--start-maximized",
    ]
    assert ui_launch["ignore_default_args"] == ["about:blank"]
    assert web_launch["args"] == []
    assert web_launch["ignore_default_args"] == []

    ui_context = factory.managers[1].playwright.chromium.context
    assert ui_context.pages[0].url == "http://127.0.0.1:5173/dashboard/?token=secret#start"
    assert ui_context.cookies == cookies
    assert factory.managers[0].playwright.chromium.context.cookies == cookies
    assert ui_context.routes[0][0] == "**/*"
    route_handler = ui_context.routes[0][1]
    local_route = FakeRoute()
    remote_route = FakeRoute()
    await route_handler(local_route, FakeRequest("http://127.0.0.1:5173/app.js"))
    await route_handler(remote_route, FakeRequest("https://example.com/tracker.js"))
    assert local_route.action == "continue"
    assert remote_route.action == ("abort", "blockedbyclient")

    with pytest.raises(BrowserError, match="cannot be navigated"):
        await service.goto("harness_ui", "https://example.com")
    with pytest.raises(BrowserError, match="loopback"):
        await service.open_application_ui("https://example.com")

    await service.close_web()
    assert factory.managers[0].playwright.stopped is True
    assert factory.managers[1].playwright.stopped is False
    assert service.session("harness_ui").started is True

    await service.stop()
    assert all(manager.playwright.stopped for manager in factory.managers)


def test_browser_session_targets_snapshot_element_ids(tmp_path):
    asyncio.run(_browser_session_targets_snapshot_element_ids(tmp_path))


async def _browser_session_targets_snapshot_element_ids(tmp_path):
    factory = PlaywrightFactory()
    session = BrowserSession(profile_dir=tmp_path / "profile", playwright_factory=factory)
    page = await session.new_page()

    snapshot = await session.snapshot()
    await session.click("1")
    await session.fill("2", "hello")
    await session.press("Enter", "3")

    assert snapshot["elements"][0]["id"] == "1"
    assert [locator.selector for locator in page.locators] == [
        f'[{BROWSER_AGENT_ID_ATTR}="1"]',
        f'[{BROWSER_AGENT_ID_ATTR}="2"]',
        f'[{BROWSER_AGENT_ID_ATTR}="3"]',
    ]
    await session.stop()


def test_browser_session_releases_driver_after_unexpected_context_close(tmp_path):
    async def run():
        factory = PlaywrightFactory()
        session = BrowserSession(profile_dir=tmp_path / "profile", playwright_factory=factory)
        await session.start()
        first = factory.managers[0]

        await first.playwright.chromium.context.close()
        await asyncio.sleep(0)

        assert session.started is False
        assert first.playwright.stopped is True

        await session.start()
        assert len(factory.managers) == 2
        await session.stop()
        assert factory.managers[1].playwright.stopped is True

    asyncio.run(run())


def test_browser_plugin_observation_is_fresh_ephemeral_provider_context(tmp_path):
    factory = PlaywrightFactory()
    service = BrowserService(tmp_path, playwright_factory=factory)
    agent = Agent(client=object())
    plugin = agent.add_extension(
        ChromiumExtension(agent, runtime_root=tmp_path, service_factory=lambda: service)
    )

    result = plugin.open_web("https://example.com")
    outputs = agent.registry("providers").outputs(channel="text")

    assert result["action"] == "open_web"
    assert result["target"] == "web"
    assert isinstance(outputs[0], ProviderOutput)
    assert "Target: web" in outputs[0].content[0].text
    assert "URL: https://example.com" in outputs[0].content[0].text
    assert '[1] button "Continue"' in outputs[0].content[0].text
    assert isinstance(outputs[1], Image)
    assert outputs[1].context_tag == "browser_screenshot"
    assert outputs[1].path.endswith("browser/screenshots/web/active_tab.png")
    assert Path(outputs[1].path).is_file()
    assert "<browser_screenshot " in outputs[1].to_api_format()["content"][1]["text"]
    assert agent.session.history == []
    assert agent.session.archive == []
    assert "chromium" in agent.registry("tools")

    factory.managers[0].playwright.chromium.context.pages[0].url = "https://example.com/changed"
    repeated = agent.registry("providers").outputs(channel="text")
    assert repeated[1].path == outputs[1].path
    assert "URL: https://example.com/changed" in repeated[0].content[0].text
    assert list((tmp_path / "browser" / "screenshots" / "web").glob("*.png")) == [
        Path(outputs[1].path),
    ]

    plugin.deactivate()
    assert all(manager.playwright.stopped for manager in factory.managers)


def test_browser_plugin_closes_web_tabs_without_touching_harness_ui(tmp_path):
    factory = PlaywrightFactory()
    service = BrowserService(tmp_path, playwright_factory=factory)
    agent = Agent(client=object())
    plugin = agent.add_extension(
        ChromiumExtension(agent, runtime_root=tmp_path, service_factory=lambda: service)
    )
    plugin.open_web("https://first.example")
    plugin.open_web("https://second.example", new_tab=True)
    plugin.controller.call("open_application_ui", "http://127.0.0.1:48887/ui/")

    closed_tab = plugin.close_tab(0)
    web_status = plugin.status("web")
    ui_status = plugin.status("harness_ui")

    assert closed_tab["closed_index"] == 0
    assert closed_tab["remaining_tabs"] == 1
    assert len(web_status["tabs"]) == 1
    assert ui_status["open"] is True
    assert len(ui_status["tabs"]) == 1

    closed_web = plugin.close_web()

    assert closed_web == {
        "status": "success",
        "action": "close_web",
        "target": "web",
        "closed": True,
    }
    assert service.sessions["web"].started is False
    assert service.sessions["harness_ui"].started is True

    plugin.deactivate()


def test_browser_rpc_client_disconnect_does_not_close_persistent_browser(tmp_path):
    asyncio.run(_browser_rpc_client_disconnect_does_not_close_persistent_browser(tmp_path))


async def _browser_rpc_client_disconnect_does_not_close_persistent_browser(tmp_path):
    factory = PlaywrightFactory()
    service = BrowserService(tmp_path, playwright_factory=factory)
    server = await BrowserRPCServer(tmp_path / "browser.sock", service).start()
    client = BrowserRPCClient(server.socket_path)

    await asyncio.to_thread(
        client.call,
        "open_application_ui",
        "http://127.0.0.1:48887/app",
    )
    before = await asyncio.to_thread(client.session_call, "harness_ui", "status")
    client.close()
    after = await asyncio.to_thread(client.session_call, "harness_ui", "status")

    assert before["open"] is True
    assert after["tabs"][0]["url"] == "http://127.0.0.1:48887/app"
    assert factory.managers[0].playwright.stopped is False

    await server.close()
    assert factory.managers[0].playwright.stopped is True
