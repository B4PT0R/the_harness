"""Application-owned credentials, origin boundary and transport access policy."""

from hmac import compare_digest
from urllib.parse import urlsplit

from the_framework.server.api.endpoints import Principal


def local_request_allowed(request, *, allowed_origins=()):
    """Reject foreign/malformed hosts and cross-origin use of local credentials.

    WebSockets use the corresponding HTTP origin. Explicit native origins are
    opt-in for token-authenticated sockets, never for browser cookies.
    """
    if len(request.headers.getlist("host")) != 1 or len(request.headers.getlist("origin")) > 1:
        return False
    host = request.headers.get("host", "")
    try:
        parsed = urlsplit(f"http://{host}")
        if (
            parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username is not None or parsed.password is not None
            or parsed.path or parsed.query or parsed.fragment
            or parsed.netloc != host
        ):
            return False
        _ = parsed.port  # Reject malformed and out-of-range ports.
    except ValueError:
        return False
    scheme = {"ws": "http", "wss": "https"}.get(request.url.scheme, request.url.scheme)
    origin = request.headers.get("origin")
    return origin is None or origin == f"{scheme}://{host}" or origin in allowed_origins


def _matches(supplied, expected):
    return isinstance(supplied, str) and compare_digest(supplied.encode(), expected.encode())


class HarnessSecurityPolicy:
    def __init__(self, *, token, browser_token, remote_clients, allowed_origins=()):
        if not token or not browser_token:
            raise ValueError("private local session tokens are required")
        self.token = token
        self.browser_token = browser_token
        self.remote_clients = remote_clients
        self.allowed_origins = frozenset(allowed_origins)

    def _local_principal(self, request, *, supplied_token=None):
        """Resolve local credentials through the same rules for all callers."""
        if _matches(supplied_token, self.token):
            return Principal(id="local-bearer", scopes=frozenset({"*"}))
        if _matches(request.cookies.get("harness_session"), self.browser_token):
            return Principal(id="local-browser", scopes=frozenset({"*"}))
        return None

    async def authenticate(self, request):
        if not local_request_allowed(request):
            return None
        authorization = request.headers.get("authorization", "")
        bearer = authorization[7:] if authorization.startswith("Bearer ") else None
        local = self._local_principal(request, supplied_token=bearer)
        if local is not None:
            return local
        remote_clients = self.remote_clients()
        client = remote_clients.authenticate(bearer) if remote_clients is not None and bearer else None
        if client is None:
            return None
        scopes = frozenset(client.get("scopes", ()))
        if {"desktop", "full_ui"} & scopes:
            scopes = frozenset({*scopes, "*"})
        return Principal(id=f"remote:{client['id']}", scopes=scopes, attributes={"client": client})

    def http_access_allowed(self, principal, request):
        """Protect private mounts and retain the paired-desktop route allowlist."""
        if principal is None:
            return False
        client = principal.attributes.get("client")
        if client is None:
            return principal.id in {"local-bearer", "local-browser"}
        service = self.remote_clients()
        return bool(
            {"desktop", "full_ui"} & set(client.get("scopes", ()))
            and service is not None
            and service.desktop_api_allowed(request.method, request.url.path)
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

    def socket_handshake(self, *, supported):
        """Select the wire protocol, then apply the shared credential boundary."""
        def authenticate(socket):
            protocols = [value.strip() for value in socket.headers.get(
                "sec-websocket-protocol", "").split(",") if value.strip()]
            if not protocols or protocols[0] not in supported:
                return None
            # Native origins require the explicit local bearer token; a cookie
            # may only authorize a same-origin browser (or an origin-less client).
            token = next((value for value in protocols[1:] if _matches(value, self.token)), None)
            origins = self.allowed_origins if token is not None else ()
            if not local_request_allowed(socket, allowed_origins=origins):
                return None
            if self._local_principal(socket, supplied_token=token) is None:
                return None
            return {"subprotocol": protocols[0]}
        return authenticate
