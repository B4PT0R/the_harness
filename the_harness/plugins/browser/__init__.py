from the_framework.plugins.browser import CHROMIUM
from the_framework.plugins.browser import BrowserConfig
from the_framework import Plugin
from .agent import ChromiumExtension

PLUGIN = Plugin({**CHROMIUM, "agent_extension": ChromiumExtension})

__all__ = ["BrowserConfig", "ChromiumExtension", "PLUGIN"]
