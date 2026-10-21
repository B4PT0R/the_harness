"""Product selection of resources cleared by a canonical session reset."""

RESET_ENTRIES = (
    "session.json",
    "relational-memory.sqlite3",
    "relational-memory.sqlite3-shm",
    "relational-memory.sqlite3-wal",
    "session.auxiliaries",
    "system-control.json",
    "agentic.json",
    "registry.json",
)

SESSION_RESET_ENTRIES = (
    "session.json", "session.auxiliaries", "system-control.json",
    "session.turn-timing.json",
)

MEMORY_RESET_ENTRIES = (
    "relational-memory.sqlite3", "relational-memory.sqlite3-shm",
    "relational-memory.sqlite3-wal", "session.auxiliaries/memory.jiminy",
)

REGISTRY_RESET_ENTRIES = ("registry.json",)
