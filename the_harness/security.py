"""Application-owned credentials, origin boundary and transport access policy."""

from hmac import compare_digest
from urllib.parse import urlsplit

from the_framework.server.api.endpoints import Principal
from the_framework.server.clients.previews import (
    authorize_preview,
    is_preview,
    preview_access,
)


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


def private_request_allowed(request, endpoint):
    if not endpoint or len(request.headers.getlist("host")) != 1 or len(request.headers.getlist("origin")) > 1:
        return False
    parsed = urlsplit(endpoint)
    host = request.headers.get("host", "")
    origin = request.headers.get("origin")
    return (parsed.scheme == "https" and parsed.hostname.endswith(".ts.net")
            and host == parsed.netloc and origin in (None, endpoint))


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

    def request_allowed(self, request):
        service = self.remote_clients()
        network = getattr(service, "network", None)
        return local_request_allowed(request) or private_request_allowed(request, getattr(network, "endpoint", None))

    async def authenticate(self, request):
        if not self.request_allowed(request):
            return None
        previews = preview_access(request)
        if local_request_allowed(request) and previews is not None and previews.cookie in request.cookies:
            principal = previews.authenticate(request)
            return principal if previews.allows_http(request) else None
        authorization = request.headers.get("authorization", "")
        bearer = authorization[7:] if authorization.startswith("Bearer ") else None
        local = self._local_principal(request, supplied_token=bearer) if local_request_allowed(request) else None
        if local is not None:
            return local
        remote_clients = self.remote_clients()
        credential = bearer or request.cookies.get("harness_mobile")
        client = remote_clients.authenticate(credential) if remote_clients is not None and credential else None
        if not bearer and client is not None and "mobile" not in client.get("scopes", ()):
            return None
        if client is None:
            return None
        scopes = frozenset(client.get("scopes", ()))
        if "mobile" in scopes:
            # Product capability for existing paired companions, not host administration.
            scopes = scopes | {"quota:write"}
        if {"desktop", "full_ui"} & scopes:
            scopes = frozenset({*scopes, "*"})
        return Principal(id=f"remote:{client['id']}", scopes=scopes, attributes={"client": client})

    def http_access_allowed(self, principal, request):
        """Protect private mounts and retain the paired-desktop route allowlist."""
        if principal is None:
            return False
        if is_preview(principal):
            return preview_access(request).allows_http(request)
        client = principal.attributes.get("client")
        if client is None:
            return principal.id in {"local-bearer", "local-browser"}
        service = self.remote_clients()
        if "mobile" in client.get("scopes", ()):
            from .plugins.client_remote.policy import mobile_api_allowed
            return mobile_api_allowed(request.method, request.url.path)
        return bool(
            {"desktop", "full_ui"} & set(client.get("scopes", ()))
            and service is not None
            and service.desktop_api_allowed(request.method, request.url.path)
        )

    async def authorize(self, principal, requirement, _request):
        if is_preview(principal):
            return authorize_preview(principal, requirement)
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
            previews = preview_access(socket)
            if previews is not None and previews.cookie in socket.cookies:
                if previews.authenticate(socket) is None or socket.url.path != '/api/v1/events':
                    return None
                return {'subprotocol': protocols[0], 'client_role': 'preview'}
            if self._local_principal(socket, supplied_token=token) is None:
                return None
            return {"subprotocol": protocols[0]}
        return authenticate
