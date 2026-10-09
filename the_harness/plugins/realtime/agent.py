"""Voice policy for the same general-purpose assistant."""
from pathlib import Path
from modict import modict
from the_framework.plugins.realtime import RealtimeConfig as GenericRealtimeConfig
from the_framework.plugins.realtime import RealtimeExtension as GenericRealtimeExtension

class RealtimeConfig(GenericRealtimeConfig):
    provider_whitelist: list[str] = modict.factory(lambda: ["relevant_memory", "persistent_registry"])

class RealtimeExtension(GenericRealtimeExtension):
    config = RealtimeConfig
    instructions_file = Path(__file__).with_name("instructions.md")
