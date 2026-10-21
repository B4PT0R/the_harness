"""Declarative hosted-UI and browser-control application surface."""

import asyncio
import secrets
import time

from fastapi.responses import JSONResponse, RedirectResponse

from the_framework.server import endpoint


class HostedUiApi:
    def __init__(
        self,
        browser,
        *,
        browser_token,
        ticket_ttl=30,
    ):
        self.browser = browser
        self.browser_token = browser_token
        self.ticket_ttl = ticket_ttl
        self.tickets = {}

    def issue_ticket(self):
        now = time.monotonic()
        for expired in [
            ticket for ticket, expiry in self.tickets.items() if expiry <= now
        ]:
            self.tickets.pop(expired, None)
        ticket = secrets.token_urlsafe(32)
        self.tickets[ticket] = now + self.ticket_ttl
        return ticket

    @endpoint(
        "get", "/ui/bootstrap",
        request={
            "type": "object",
            "properties": {"ticket": {"type": "string"}},
            "additionalProperties": False,
        },
        authenticated=False,
    )
    def bootstrap(self, ticket=""):
        """Exchange one short-lived UI ticket for a browser session cookie."""
        expiry = self.tickets.pop(ticket, None)
        if expiry is None or expiry <= time.monotonic():
            return JSONResponse(
                {"error": "invalid or expired UI ticket"}, status_code=401,
            )
        response = RedirectResponse("/ui/")
        response.set_cookie(
            "harness_session",
            self.browser_token,
            httponly=True,
            samesite="strict",
            secure=False,
            path="/",
        )
        return response

    @endpoint(
        "post", "/api/v1/ui/open",
        authorization={"scope": "ui:write"},
        context="call",
    )
    async def open(self, call):
        """Open the hosted interface in the persistent local browser runtime."""
        if call.application.surface_service.active_path("main") is None:
            return JSONResponse(
                {"error": "interface unavailable: no published release"}, status_code=503,
            )
        ticket = self.issue_ticket()
        base_url = str(call.request.base_url).rstrip("/")
        bootstrap_url = f"{base_url}/ui/bootstrap?ticket={ticket}"
        try:
            await asyncio.to_thread(
                self.browser.call, "open_application_ui", bootstrap_url,
            )
        except Exception as error:
            self.tickets.pop(ticket, None)
            return JSONResponse(
                {"error": f"browser service unavailable: {error}"},
                status_code=503,
            )
        return {"status": "opened", "url": f"{base_url}/ui/"}

    def _show_browser(self):
        status = self.browser.session_call("web", "status")
        if not status["tabs"]:
            self.browser.call("open_web", "https://www.google.com")
            status = self.browser.session_call("web", "status")
        active = next(tab["index"] for tab in status["tabs"] if tab["active"])
        self.browser.session_call("web", "select_tab", active)

    @endpoint(
        "post", "/api/v1/browser/open",
        authorization={"scope": "browser:write"},
    )
    async def open_browser(self):
        """Open or foreground the local browser, preserving its existing tabs."""
        try:
            await asyncio.to_thread(self._show_browser)
        except Exception as error:
            return JSONResponse(
                {"error": f"browser service unavailable: {error}"}, status_code=503,
            )
        return {"status": "opened"}

    @endpoint(
        "post", "/api/v1/browser/open-external",
        request={
            "type": "object",
            "properties": {"url": {"type": "string", "minLength": 1}},
            "required": ["url"],
            "additionalProperties": False,
        },
        authorization={"scope": "browser:write"},
    )
    async def open_external(self, url):
        """Open one explicitly HTTP(S) URL in a new browser tab."""
        if not url.startswith(("http://", "https://")):
            return JSONResponse(
                {"error": "an HTTP(S) URL is required"}, status_code=422,
            )
        try:
            await asyncio.to_thread(self.browser.call, "open_web", url, new_tab=True)
        except Exception as error:
            return JSONResponse(
                {"error": f"browser service unavailable: {error}"},
                status_code=503,
            )
        return {"status": "opened"}
