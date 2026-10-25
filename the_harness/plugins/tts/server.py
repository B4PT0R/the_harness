"""Direct playback is a transient client operation, never a conversation item."""

from urllib.parse import urlsplit


class TTSPlayback:
    def __init__(self, clients):
        self.clients = clients

    async def handle(self, method, payload):
        if method != "play":
            raise ValueError(f"Unknown TTS operation: {method}")
        src = payload.get("src", "")
        if not isinstance(src, str):
            raise ValueError("Playback requires an authenticated bucket asset")
        url = urlsplit(src)
        if (not src.startswith("/api/v1/bucket/") or url.netloc or url.scheme
                or url.query or url.fragment or ".." in src or "\\" in src
                or "%" in src or any(char.isspace() for char in src)):
            raise ValueError("Playback requires an authenticated bucket asset")
        return await self.clients.request("audio.play", {"src": src})


def build_service(runtime, canonical_transport):
    service = TTSPlayback(canonical_transport.clients)
    runtime.bridge.register("tts", service.handle)
    return service
