import asyncio
import base64
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

from PIL import Image as Raster

from the_framework.agent import (
    AgentExtension, AgentResponseItemAdded, Artifact, Image, ImageGenerationTool,
    hook, tool,
)
from the_framework.agent.models.responses import ImageGenerationCall


class ImagesExtension(AgentExtension):
    name = "images"
    description = "Backend image creation/editing and local image inspection."
    instructions_file = "instructions.md"

    def load(self):
        if self.loaded:
            return self
        super().load()
        self._temporary = None
        if self.agent.session_root is None:
            self._temporary = TemporaryDirectory(prefix="harness-images-")
        self.root = (self.agent.session_root / "images" if self.agent.session_root
                     else Path(self._temporary.name))
        generation = ImageGenerationTool()
        for key, value in list(generation.items()):
            if value is None:
                generation.pop(key)
        self._contributions.append(("tools", generation))
        return self

    def shutdown(self):
        if self._temporary is not None:
            self._temporary.cleanup()

    def _store(self, data):
        """Validate raster bytes and freeze them under a content-addressed name."""
        with Raster.open(BytesIO(data)) as image:
            suffix = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp", "GIF": ".gif"}.get(image.format)
            if suffix is None:
                raise ValueError("Images support PNG, JPEG, WebP and GIF files.")
            image.verify()
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / (sha256(data).hexdigest() + suffix)
        if not path.exists():
            with NamedTemporaryFile(dir=self.root, delete=False) as stream:
                temporary = Path(stream.name)
                try:
                    stream.write(data)
                    stream.close()
                    temporary.replace(path)
                finally:
                    temporary.unlink(missing_ok=True)
        return path

    @tool
    async def inspect_image(self, path: str, description: str):
        """Load a local image for vision or as a reference for image_generation editing.

        This adds a stable vision input, not a chat presentation. Describe why
        the image is being inspected or how it should guide the requested edit.
        """
        source = Path(path).expanduser().resolve(strict=True)
        stored = await asyncio.to_thread(lambda: self._store(source.read_bytes()))
        return Image(path=str(stored), description=description, context_tag="local_image")

    @hook
    def on_event(self, event):
        if not isinstance(event, AgentResponseItemAdded) or not isinstance(event.item, ImageGenerationCall):
            return event
        item = event.item
        if item.get("status") != "completed" or not item.get("result"):
            return event
        path = self._store(base64.b64decode(item["result"], validate=True))
        event.item = Image(
            id=item["id"], generation_id=item["id"], path=str(path),
            description=item.get("revised_prompt") or "Backend-generated image",
            parameters={key: value for key, value in item.items()
                        if key not in {"result", "type", "id", "revised_prompt"}},
            context_tag="image_generation_result",
        )
        return event

    @hook
    async def after_generation(self, payload):
        # Recover unpublished results after a restart or a failed publication too.
        history = list(self.agent.session.history)
        published = {item.payload.get("generation_id") for item in history
                     if isinstance(item, Artifact) and item.kind == "image"}
        for item in history:
            if (not isinstance(item, Image) or item.context_tag != "image_generation_result"
                    or not item.generation_id or item.generation_id in published):
                continue
            asset = await self.agent.bridge.call(
                "artifacts", "publish", {"kind": "image", "payload": {
                    "path": item.path, "title": "Generated image",
                    "description": item.description, "generation_id": item.generation_id,
                }}, timeout_ms=120_000,
            )
            self.agent.add_response_item(Artifact(kind="image", payload=asset))
            published.add(item.generation_id)
        return payload
