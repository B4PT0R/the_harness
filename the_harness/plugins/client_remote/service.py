"""Product hooks over the reusable remote-client transport."""

from the_framework.server.clients.remote import ClientRemoteService as GenericRemoteService

from .policy import RemoteDesktopAccess


class ClientRemoteService(GenericRemoteService):
    def __init__(self, *args, desktop_access=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.desktop_access = desktop_access or RemoteDesktopAccess()

    async def start(self):
        self.desktop_access.freeze()
        await super().start()

    def desktop_api_allowed(self, method, path):
        return self.desktop_access.allowed(method, path)
