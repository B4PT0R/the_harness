import asyncio

from starlette.requests import Request

from the_harness.security import HarnessSecurityPolicy


class Clients:
    def authenticate(self, token):
        if token == "remote":
            return {"id": "phone", "scopes": ["chat"]}
        if token == "desktop":
            return {"id": "laptop", "scopes": ["desktop", "full_ui"]}
        return None


def request(*, authorization=None, cookie=None):
    headers = []
    if authorization:
        headers.append((b"authorization", authorization.encode()))
    if cookie:
        headers.append((b"cookie", cookie.encode()))
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers})


def test_harness_security_distinguishes_local_and_scoped_remote_callers():
    async def scenario():
        policy = HarnessSecurityPolicy(
            token="local",
            browser_token="browser",
            remote_clients=Clients,
        )
        local = await policy.authenticate(request(authorization="Bearer local"))
        browser = await policy.authenticate(request(cookie="harness_session=browser"))
        remote = await policy.authenticate(request(authorization="Bearer remote"))
        desktop = await policy.authenticate(request(authorization="Bearer desktop"))

        assert local.id == "local-bearer" and "*" in local.scopes
        assert browser.id == "local-browser" and "*" in browser.scopes
        assert remote.id == "remote:phone" and remote.scopes == {"chat"}
        assert "*" in desktop.scopes
        assert await policy.authorize(remote, {"scope": "chat"}, request())
        assert not await policy.authorize(remote, {"scope": "images:read"}, request())
        assert await policy.authorize(desktop, {"scope": "images:read"}, request())
        assert await policy.authenticate(request(authorization="Bearer bad")) is None

    asyncio.run(scenario())
