"""Application-owned selective reset endpoints."""
from the_framework.server import endpoint
from the_framework.server.api.endpoints import HttpError


class MemoryResetApi:
    def __init__(self, runtime):
        self.runtime = runtime

    @endpoint("delete", "/api/v1/memory", authorization={"scope": "memory:write"}, response={"type": "object"})
    async def reset(self):
        try:
            return await self.runtime.reset_memory()
        except RuntimeError as error:
            raise HttpError(500, "memory_reset_failed", str(error)) from error
