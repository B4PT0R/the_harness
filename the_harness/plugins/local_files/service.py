"""Private editor preferences and explicit host-side file opening; never a shell."""

import asyncio
import logging
import os
import re
import shutil
import stat
from pathlib import Path

from the_framework.server import endpoint
from the_framework.server.api.endpoints import HttpError
from the_framework.utils.persistence import MappingStore

logger = logging.getLogger(__name__)
EDITOR_SCHEMA = {"type": "string", "enum": ["system", "vscode"]}
TEXT_EXTENSIONS = frozenset(
    ".txt .md .markdown .rst .log .csv .tsv .json .jsonl .yaml .yml .toml .ini .cfg "
    ".conf .xml .html .css .scss .js .jsx .ts .tsx .py .pyi .sh .bash .sql .c .h "
    ".cpp .hpp .rs .go .java .kt .swift .rb .php .tex .env".split()
)
TEXT_NAMES = frozenset({"Makefile", "Dockerfile", "LICENSE", "README", ".gitignore", ".env"})


def local_resource(raw):
    if not raw.startswith(("/", "~/")) or any(ord(char) < 32 for char in raw):
        raise HttpError(422, "invalid_file_path", "Un chemin absolu ou ~/ est nécessaire.")
    path = Path(raw).expanduser()
    try:
        path = path.resolve(strict=True)
        mode = path.stat().st_mode
        if stat.S_ISDIR(mode):
            return path, "directory"
        if not stat.S_ISREG(mode):
            raise HttpError(422, "not_regular_file", "Seuls les fichiers ordinaires et dossiers peuvent être ouverts.")
        if path.suffix.lower() not in TEXT_EXTENSIONS and path.name not in TEXT_NAMES:
            return path.parent, "directory"
        # O_NONBLOCK prevents a replaced file/FIFO from blocking the server.
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise HttpError(422, "not_regular_file", "Seuls les fichiers ordinaires peuvent être ouverts.")
            sample = stream.read(8192)
    except FileNotFoundError as error:
        raise HttpError(404, "file_not_found", "Ce fichier n’existe plus.") from error
    except (OSError, RuntimeError) as error:
        raise HttpError(422, "file_unreadable", "Ce fichier n’est pas accessible.") from error
    if b"\0" in sample or any(byte < 32 and byte not in (9, 10, 12, 13) for byte in sample):
        return path.parent, "directory"
    return path, "text"


async def run_editor_command(*args):
    process = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        output, _ = await asyncio.wait_for(process.communicate(), timeout=5)
    except (TimeoutError, asyncio.CancelledError):
        if process.returncode is None:
            process.kill()
        await process.communicate()
        raise
    if process.returncode:
        raise OSError("editor command failed")
    return output.decode("utf-8", errors="replace").strip()


async def launch_editor(editor, path):
    if editor == "vscode":
        executable = shutil.which("code")
        if not executable:
            raise HttpError(503, "editor_unavailable", "VS Code est indisponible : la commande code est introuvable.")
        await run_editor_command(executable, "--reuse-window", str(path))
        return
    # Use the default *text editor*, not the file's MIME association: an HTML
    # file must not open in a browser, nor a shell script execute on a click.
    mime, gio = shutil.which("xdg-mime"), shutil.which("gio")
    if not mime or not gio:
        raise HttpError(503, "editor_unavailable", "L’éditeur système nécessite xdg-mime et gio.")
    desktop_id = await run_editor_command(mime, "query", "default", "text/plain")
    if not re.fullmatch(r"[\w.-]+\.desktop", desktop_id):
        raise HttpError(503, "editor_unavailable", "Aucun éditeur par défaut n’est associé aux fichiers texte.")
    roots = [Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")]
    roots += [Path(root) for root in (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":") if root]
    desktop = next((root / "applications" / desktop_id for root in roots if (root / "applications" / desktop_id).is_file()), None)
    if desktop is None:
        raise HttpError(503, "editor_unavailable", "L’application de l’éditeur système est introuvable.")
    await run_editor_command(gio, "launch", str(desktop), path.as_uri())


async def launch_resource(kind, path, editor):
    if kind == "text":
        await launch_editor(editor, path)
    else:
        executable = shutil.which("gio")
        if not executable:
            raise HttpError(503, "explorer_unavailable", "L’explorateur système nécessite gio.")
        await run_editor_command(executable, "open", path.as_uri())


class LocalFilesService:
    def __init__(self, settings_path, *, launcher=launch_resource):
        self.store = MappingStore(settings_path)
        self.launcher = launcher
        self.lock = asyncio.Lock()
        self.editor = "system"
        try:
            saved = self.store.load().get("editor", "system")
            if saved not in ("system", "vscode"):
                raise ValueError("invalid editor preference")
            self.editor = saved
        except (OSError, ValueError) as error:
            logger.warning("file editor settings could not be read: %s", error)

    @staticmethod
    def _local(call):
        if call.principal.id not in {"local-browser", "local-bearer"}:
            raise HttpError(403, "local_only", "L’ouverture de fichiers est réservée à l’interface locale.")

    @endpoint("get", "/api/v1/local-files/settings", response={"type": "object"},
              authorization={"scope": "settings:read"}, context="call")
    def settings(self, call):
        self._local(call)
        return {"editor": self.editor}

    @endpoint("put", "/api/v1/local-files/settings",
              request={"type": "object", "properties": {"editor": EDITOR_SCHEMA},
                       "required": ["editor"], "additionalProperties": False},
              response={"type": "object"}, authorization={"scope": "settings:write"}, context="call")
    async def update(self, editor, call):
        self._local(call)
        if editor not in ("system", "vscode"):
            raise HttpError(422, "invalid_editor", "Choisissez l’éditeur système ou VS Code.")
        async with self.lock:
            await asyncio.to_thread(self.store.save, {"editor": editor})
            self.editor = editor
        return {"editor": self.editor}

    @endpoint("post", "/api/v1/local-files/open",
              request={"type": "object", "properties": {"path": {"type": "string", "minLength": 1, "maxLength": 4096}},
                       "required": ["path"], "additionalProperties": False},
              response={"type": "object"}, authorization={"scope": "host:files:open"}, context="call")
    async def open(self, path, call):
        self._local(call)
        target, kind = await asyncio.to_thread(local_resource, path)
        editor = self.editor
        try:
            await self.launcher(kind, target, editor)
        except (OSError, TimeoutError) as error:
            raise HttpError(503, "editor_launch_failed", "Impossible de lancer l’application choisie.") from error
        return {"status": "opened", "kind": kind, "editor": editor if kind == "text" else None, "path": str(target)}
