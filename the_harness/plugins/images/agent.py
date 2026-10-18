import asyncio
import base64
from pathlib import Path
from tempfile import TemporaryDirectory

from the_framework.agent import (
    AgentExtension, AgentResponseItemAdded, Artifact, Image, ImageGenerationTool,
    hook, tool,
)
from the_framework.agent.models.responses import ImageGenerationCall


class ImagesExtension(AgentExtension):
    name = "images"
    description = "Backend image creation/editing and local or remote image inspection."
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

    @tool
    async def inspect_image(self, source: str, description: str):
        """Load a local path or HTTP(S) image URL for vision or image_generation editing.

        URLs are downloaded and validated locally before context injection; the
        API receives base64, never the remote URL. This freezes a vision input,
        not a chat presentation. Describe why the image is being inspected.
        """
        return await asyncio.to_thread(
            Image.from_source, source, directory=self.root,
            description=description, context_tag="inspected_image",
        )

    @hook
    def on_event(self, event):
        if not isinstance(event, AgentResponseItemAdded) or not isinstance(event.item, ImageGenerationCall):
            return event
        item = event.item
        if item.get("status") != "completed" or not item.get("result"):
            return event
        event.item = Image.from_source(
            base64.b64decode(item["result"], validate=True), directory=self.root,
            id=item["id"], generation_id=item["id"],
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
