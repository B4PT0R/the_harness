"""Declarative HTTP surface for The Harness private remote clients."""

import asyncio
from urllib.parse import urlparse

from starlette.websockets import WebSocketDisconnect
from the_framework.agent.runtime.protocol import (
    InterruptRequest,
    PromptRequest,
    SessionPageRequest,
    StatusRequest,
)
from the_framework.server import endpoint
from the_framework.server.api.endpoints import HttpError
from the_framework.server.api.websockets import WebSocketEndpoint
from the_framework.server.clients.remote import PROTOCOL_VERSION
from the_framework.utils.ids import timestamp_id

from ...security import local_request_allowed
from .policy import RemoteProjection


class ClientRemoteApi:
    def __init__(self, service, ingress, *, advertised_endpoint=None):
        self.service = service
        self.runtime = service.runtime
        self.advertised_endpoint = advertised_endpoint
        self.ingress = ingress
        self.events_socket = WebSocketEndpoint(
            path="/remote/v1/events",
            handler=self.serve_events,
            name="remote_events",
            handshake=self.event_handshake,
        )
        self.application_socket = WebSocketEndpoint(
            path="/remote/v1/application",
            handler=self.serve_application,
            name="remote_application",
            handshake=self.application_handshake,
        )

    def websocket_declarations(self):
        return (self.events_socket, self.application_socket)

    @staticmethod
    def _client(call):
        client = (call.principal.attributes or {}).get("client")
        if client is None:
            raise HttpError(401, "unauthorized", "Remote client is required")
        return client

    @staticmethod
    def _protocols(socket):
        return [
            value.strip()
            for value in socket.headers.get("sec-websocket-protocol", "").split(",")
            if value.strip()
        ]

    def _remote_handshake(self, socket, subprotocol):
        if not local_request_allowed(socket):
            return None
        protocols = self._protocols(socket)
        if len(protocols) != 2 or protocols[0] != subprotocol:
            return None
        client = self.service.authenticate(protocols[1])
        if client is None:
            return None
        return {"client": client, "subprotocol": protocols[0]}

    def event_handshake(self, socket):
        connection = self._remote_handshake(socket, self.service.event_subprotocol)
        if connection is None:
            return None
        try:
            after = int(socket.query_params.get("after", "0"))
        except (TypeError, ValueError):
            return None
        if after < 0:
            return None
        return {
            **connection,
            "after": after,
            "server_instance_id": socket.query_params.get("server_instance_id"),
        }

    def application_handshake(self, socket):
        return self._remote_handshake(socket, self.service.application_subprotocol)

    async def serve_events(self, socket, connection):
        try:
            await self.service.serve_events(
                socket,
                connection["client"],
                connection["after"],
                connection["server_instance_id"],
                subprotocol=connection["subprotocol"],
            )
        except WebSocketDisconnect:
            return

    async def serve_application(self, socket, connection):
        try:
            await self.service.serve_application(
                socket,
                connection["client"],
                subprotocol=connection["subprotocol"],
            )
        except WebSocketDisconnect:
            return

    @endpoint(
        "get", "/api/v1/client-remote",
        response={"type": "object"},
        authorization={"scope": "remote-clients:read"},
    )
    def status(self):
        """Return paired private clients and the current remote transport state."""
        self.service.purge_pairings()
        return {
            "version": PROTOCOL_VERSION,
            "suggested_endpoint": self.advertised_endpoint,
            "clients": self.service.clients.list(),
            "pending_pairings": len(self.service.pairings),
            "latest_event_sequence": self.service.sequence,
        }

    @endpoint(
        "post", "/api/v1/client-remote/pairings",
        request={
            "type": "object",
            "properties": {"endpoint": {"type": ["string", "null"]}},
            "additionalProperties": False,
        },
        response={"type": "object"},
        authorization={"scope": "remote-clients:write"},
        context="call",
    )
    def create_pairing(self, call, endpoint=None):
        """Create one short-lived, single-use private-client pairing."""
        parsed = urlparse(str(endpoint)) if endpoint else None
        if self.advertised_endpoint and (
            endpoint is None
            or parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        ):
            endpoint = self.advertised_endpoint
        if endpoint is None:
            endpoint = str(call.request.base_url).rstrip("/")
        return self.service.create_pairing(endpoint)

    @endpoint(
        "delete", "/api/v1/client-remote/clients/{client_id}",
        request={
            "type": "object",
            "properties": {"client_id": {"type": "string", "minLength": 1}},
            "required": ["client_id"],
            "additionalProperties": False,
        },
        response={"type": "object"},
        authorization={"scope": "remote-clients:write"},
    )
    async def revoke(self, client_id):
        """Revoke a private client and its active connections immediately."""
        if not await self.service.revoke_client(client_id):
            raise HttpError(404, "unknown_remote_client", "Unknown remote client")
        return {"status": "revoked", "client_id": client_id}

    @endpoint(
        "post", "/remote/v1/pairings/claim",
        request={
            "type": "object",
            "properties": {
                "version": {"type": "integer"},
                "pairing_id": {"type": "string"},
                "secret": {"type": "string"},
                "device_name": {"type": "string"},
                "platform": {"type": "string"},
            },
            "required": ["version", "pairing_id", "secret", "device_name"],
            "additionalProperties": False,
        },
        response={"type": "object"},
        authenticated=False,
    )
    def claim(self, version, pairing_id, secret, device_name, platform="android"):
        """Exchange a valid pairing secret for one durable client credential."""
        if version != PROTOCOL_VERSION:
            raise HttpError(
                422,
                "unsupported_protocol_version",
                "Unsupported remote protocol version",
            )
        try:
            return self.service.claim(pairing_id, secret, device_name, platform)
        except ValueError as error:
            raise HttpError(422, "invalid_pairing", "Pairing could not be claimed") from error

    @endpoint(
        "get", "/remote/v1/bootstrap",
        request={
            "type": "object",
            "properties": {
                "before": {"type": ["string", "null"]},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            "additionalProperties": False,
        },
        response={"type": "object"},
        context="call",
    )
    async def bootstrap(self, call, before=None, limit=50):
        """Load the canonical session and current application projection."""
        client = self._client(call)
        session_page, agent_status = await asyncio.gather(
            self.runtime.request(SessionPageRequest(
                id=timestamp_id(), before=before, limit=limit, projection="activity",
            ), timeout=15),
            self.runtime.request(StatusRequest(id=timestamp_id())),
        )
        return {
            "version": PROTOCOL_VERSION,
            "client": self.service.clients.public(client),
            "event_cursor": self.service.sequence,
            "server_instance_id": self.service.instance_id,
            "session": RemoteProjection().session_page(client["id"], session_page),
            "agent_status": agent_status,
            "application": {"connected": self.runtime.bridge.connected},
            "capabilities": self.service.lease_status(),
            "assistant": {},
        }

    @endpoint(
        "get", "/remote/v1/state",
        response={"type": "object"},
        context="call",
    )
    async def state(self, call):
        """Return the current server-owned assistant state projection."""
        self._client(call)
        return {}

    @endpoint(
        "get", "/remote/v1/notifications/wait",
        request={
            "type": "object",
            "properties": {
                "after": {"type": ["integer", "null"], "minimum": 0},
                "server_instance_id": {"type": ["string", "null"]},
                "timeout": {"type": "number", "minimum": 1, "maximum": 55},
            },
            "additionalProperties": False,
        },
        response={"type": "object"},
        context="call",
    )
    async def wait_notification(
        self, call, after=None, server_instance_id=None, timeout=55,
    ):
        """Wait for lightweight committed-message signals for a headless client."""
        self._client(call)
        return await self.service.wait_for_notification(
            after=after,
            server_instance_id=server_instance_id,
            timeout=timeout,
        )

    @endpoint(
        "post", "/remote/v1/commands",
        request={
            "type": "object",
            "properties": {
                "id": {"type": ["string", "null"]},
                "command_id": {"type": ["string", "null"]},
                "prompt": {"type": "string"},
                "append_prompt": {"type": "boolean"},
            },
            "required": ["prompt"],
            "additionalProperties": False,
        },
        status_code=202,
        context="call",
    )
    async def prompt(self, call, prompt, id=None, command_id=None, append_prompt=True):
        """Submit one idempotent prompt to the active canonical modality."""
        client = self._client(call)
        if append_prompt and not prompt.strip():
            raise HttpError(422, "invalid_request", "prompt is required")
        command_id = command_id or id

        async def submit():
            result = await self.ingress.submit(PromptRequest(
                id=command_id, prompt=prompt, append_prompt=append_prompt,
            ))
            return {**result, "command_id": command_id, "status": "submitted"}

        try:
            return await self.service.submit_idempotent(
                client["id"],
                command_id,
                {"type": "prompt", "prompt": prompt, "append_prompt": append_prompt},
                submit,
            )
        except ValueError as cause:
            raise HttpError(409, "command_conflict", str(cause)) from cause

    @endpoint(
        "post", "/remote/v1/interrupt",
        request={
            "type": "object",
            "properties": {
                "id": {"type": ["string", "null"]},
                "command_id": {"type": ["string", "null"]},
                "reason": {"type": ["string", "null"]},
            },
            "additionalProperties": False,
        },
        status_code=202,
        context="call",
    )
    async def interrupt(self, call, id=None, command_id=None, reason=None):
        """Submit one idempotent canonical interrupt."""
        client = self._client(call)
        command_id = command_id or id

        async def submit():
            command = InterruptRequest(id=command_id, reason=reason)
            await self.runtime.submit(command)
            return {
                "id": command.id,
                "command_id": command_id,
                "status": "submitted",
            }

        try:
            return await self.service.submit_idempotent(
                client["id"],
                command_id,
                {"type": "interrupt", "reason": reason},
                submit,
            )
        except ValueError as cause:
            raise HttpError(409, "command_conflict", str(cause)) from cause
