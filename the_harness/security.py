"""The Harness authentication policy for declarative server endpoints."""

from the_framework.server.api.endpoints import Principal


class HarnessSecurityPolicy:
    def __init__(self, *, token, browser_token, remote_clients):
        self.token = token
        self.browser_token = browser_token
        self.remote_clients = remote_clients

    async def authenticate(self, request):
        authorization = request.headers.get("authorization", "")
        if authorization == f"Bearer {self.token}":
            return Principal(id="local-bearer", scopes=frozenset({"*"}))
        if request.cookies.get("harness_session") == self.browser_token:
            return Principal(id="local-browser", scopes=frozenset({"*"}))
        if not authorization.startswith("Bearer "):
            return None
        remote_clients = self.remote_clients()
        client = (
            remote_clients.authenticate(authorization[7:])
            if remote_clients is not None else None
        )
        if client is None:
            return None
        scopes = frozenset(client.get("scopes", ()))
        if {"desktop", "full_ui"} & scopes:
            scopes = frozenset({*scopes, "*"})
        return Principal(
            id=f"remote:{client['id']}",
            scopes=scopes,
            attributes={"client": client},
        )

    async def authorize(self, principal, requirement, _request):
        if requirement is None or "*" in principal.scopes:
            return True
        if isinstance(requirement, str):
            return requirement in principal.scopes
        if isinstance(requirement, dict):
            scope = requirement.get("scope")
            return scope is None or scope in principal.scopes
        if isinstance(requirement, (list, tuple, set, frozenset)):
            return set(requirement) <= principal.scopes
        return False
