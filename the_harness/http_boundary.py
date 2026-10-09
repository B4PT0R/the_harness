"""Product HTTP access boundary and hosted-shell cache policy."""

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware

from the_framework import ServerExtension


class HarnessAccessMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        token,
        browser_token,
        remote_clients,
    ):
        super().__init__(app)
        self.token = token
        self.browser_token = browser_token
        self.remote_clients = remote_clients

    def remote_bearer(self, request):
        authorization = request.headers.get("authorization", "")
        if not authorization.startswith("Bearer "):
            return None
        remote_clients = self.remote_clients()
        return (
            remote_clients.authenticate(authorization[7:])
            if remote_clients is not None else None
        )

    def remote_desktop_allowed(self, method, path):
        service = self.remote_clients()
        return service is not None and service.desktop_api_allowed(method, path)

    async def dispatch(self, request, call_next):
        path = request.url.path
        if path in {"/.well-known/assetlinks.json", "/ui/bootstrap"}:
            return await call_next(request)
        if path in {"/remote-ui", "/quest-ui"} or path.startswith((
            "/remote-ui/", "/quest-ui/",
        )):
            response = await call_next(request)
            if response.headers.get("content-type", "").startswith("text/html"):
                response.headers["Cache-Control"] = (
                    "no-cache, no-store, must-revalidate"
                )
                response.headers["Pragma"] = "no-cache"
            return response
        if path.startswith("/remote/v1/"):
            return await call_next(request)
        bearer = request.headers.get("authorization") == f"Bearer {self.token}"
        browser_session = (
            request.cookies.get("harness_session") == self.browser_token
        )
        remote_client = self.remote_bearer(request)
        remote_desktop = (
            remote_client is not None
            and {"desktop", "full_ui"} & set(remote_client.get("scopes", ()))
            and self.remote_desktop_allowed(request.method, path)
        )
        if not bearer and not browser_session and not remote_desktop:
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        return await call_next(request)


def access_boundary(*, token, browser_token, remote_clients):
    """HTTP boundary shared by local and explicitly paired clients."""
    return ServerExtension(
        name="http_boundary",
        middleware=(
            (
                CORSMiddleware,
                {
                    "allow_origins": [
                        "https://localhost",
                        "capacitor://localhost",
                        "http://localhost",
                    ],
                    "allow_methods": [
                        "GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS",
                    ],
                    "allow_headers": ["Authorization", "Content-Type", "Range"],
                    "expose_headers": [
                        "Accept-Ranges", "Content-Length", "Content-Range",
                    ],
                },
            ),
            (
                HarnessAccessMiddleware,
                {
                    "token": token,
                    "browser_token": browser_token,
                    "remote_clients": remote_clients,
                },
            ),
        ),
    )
