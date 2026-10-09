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
    headers = [(b"host", b"127.0.0.1:48887")]
    if authorization:
        headers.append((b"authorization", authorization.encode()))
    if cookie:
        headers.append((b"cookie", cookie.encode()))
    return Request({"type": "http", "method": "GET", "path": "/", "scheme": "http", "headers": headers})


def test_local_sessions_reject_cross_origin_and_rebinding():
    from the_harness.security import local_request_allowed
    for host, origin, allowed in (
        ("127.0.0.1:48887", None, True),
        ("127.0.0.1:48887", "http://127.0.0.1:48887", True),
        ("localhost:48887", "https://evil.example", False),
        ("evil.example:48887", None, False),
        ("127.0.0.1:48887", "http://127.0.0.1:48888", False),
    ):
        req = request(cookie="harness_session=browser")
        req.scope["headers"] = [(b"host", host.encode())]
        if origin: req.scope["headers"].append((b"origin", origin.encode()))
        assert local_request_allowed(req) is allowed


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
