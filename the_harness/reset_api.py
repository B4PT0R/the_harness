"""Application-owned selective reset endpoints."""
from the_framework.server import endpoint
from the_framework.server.api.endpoints import HttpError


class SelectiveResetApi:
    def __init__(self, runtime):
        self.runtime = runtime

    @endpoint("delete", "/api/v1/memory", authorization={"scope": "memory:write"}, response={"type": "object"})
    async def reset_memory(self):
        try:
            return await self.runtime.reset_memory()
        except RuntimeError as error:
            raise HttpError(500, "memory_reset_failed", str(error)) from error

    @endpoint("delete", "/api/v1/registry", authorization={"scope": "registry:write"}, response={"type": "object"})
    async def reset_registry(self):
        try:
            return await self.runtime.reset_registry()
        except RuntimeError as error:
            raise HttpError(500, "registry_reset_failed", str(error)) from error
