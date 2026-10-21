"""Canonical declarative identity of The Harness application."""

from importlib.metadata import version as package_version
from pathlib import Path

from the_framework import (
    Application,
    ClientSurface,
    Plugin,
)
from the_framework.plugins.agentic import AGENTIC
from the_framework.plugins.bash import BASH
from the_framework.plugins.registry import REGISTRY
from the_framework.plugins.web_search import WEB_SEARCH

from .agent_definition import ASSISTANT_AGENT
from .http_boundary import access_boundary
from .plugins.browser import PLUGIN as CHROMIUM
from the_framework.plugins.artifacts import ARTIFACTS
from .plugins.client_remote import PLUGIN as CLIENT_REMOTE
from .plugins.desktop_notifications import PLUGIN as DESKTOP_NOTIFICATIONS
from .plugins.hosted_ui import PLUGIN as HOSTED_UI
from .plugins.local_files import PLUGIN as LOCAL_FILES
from .plugins.images import PLUGIN as IMAGES
from .plugins.memory import PLUGIN as MEMORY
from the_framework.plugins.realtime import REALTIME as GENERIC_REALTIME
from .plugins.realtime.agent import RealtimeExtension
from the_framework.plugins.scheduler import SCHEDULER
from the_framework.plugins.system import SYSTEM

PROJECT_ROOT = Path(__file__).parents[1]


application = Application(
    name="The Harness",
    version=package_version("the-harness"),
    agents=(ASSISTANT_AGENT,),
    server_extensions=(access_boundary(),),
    plugins=(
        MEMORY,
        Plugin({**GENERIC_REALTIME, "agent_extension": RealtimeExtension}),
        DESKTOP_NOTIFICATIONS,
        LOCAL_FILES,
        CLIENT_REMOTE,
        HOSTED_UI,
        ARTIFACTS,
        IMAGES,
        BASH,
        WEB_SEARCH,
        AGENTIC,
        SCHEDULER,
        CHROMIUM,
        Plugin({**SYSTEM, "agent_binding_required": True}),
        REGISTRY,
    ),
    surfaces=(ClientSurface(
        source=PROJECT_ROOT,
        build=("npm", "run", "build:surface"),
        artifact="desktop/.surface-build",
        server_routes=("/ui/bootstrap",),
        timeout_seconds=600,
    ),),
    docs_url=None,
)


__all__ = ["application"]
