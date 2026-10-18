"""Protect the local HTTP surface with the application's security policy."""

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from the_framework import ServerExtension
from the_framework.server.clients.previews import preview_access

from .security import local_request_allowed


class HarnessAccessMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        security = request.app.state.application.access_policy
        if not local_request_allowed(request):
            return JSONResponse({"error": "untrusted host or origin"}, status_code=403)
        # Ticket exchange and remote pairing are explicitly public declarations.
        # Other remote endpoints enforce their own credentials/scopes through
        # the Framework registry. Private static mounts need this outer guard.
        previews = preview_access(request)
        if request.url.path == "/ui/bootstrap" or request.url.path.startswith("/remote/v1/") or (previews is not None and previews.is_exchange(request.url.path)):
            return await call_next(request)
        principal = await security.authenticate(request)
        if not security.http_access_allowed(principal, request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        return await call_next(request)


def access_boundary():
    return ServerExtension(
        name="http_boundary",
        middleware=((HarnessAccessMiddleware, {}),),
    )
