"""Bind the reusable browser plugin to this application's runtime directory."""

from the_framework.plugins.browser import ChromiumExtension as GenericChromiumExtension
from ...runtime_paths import bootstrap_root


class ChromiumExtension(GenericChromiumExtension):
    def __init__(self, agent, *, runtime_root=None, service_factory=None):
        super().__init__(
            agent,
            runtime_root=runtime_root if runtime_root is not None else bootstrap_root(),
            service_factory=service_factory,
        )
