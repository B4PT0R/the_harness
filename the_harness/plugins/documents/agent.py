"""Keep heavy document dependencies and conversion failures outside the worker."""

import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import signal
from tempfile import TemporaryDirectory

from the_framework.agent import AgentExtension, tool
from the_framework.agent.models.config import Config

RUNTIME = Path(__file__).parent / "runtime"
MAX_FILE_BYTES = 100 * 1024 * 1024


class DocumentsConfig(Config):
    python: str = ""  # Override for an externally installed Docling environment.
    timeout_seconds: int = 300


class DocumentsExtension(AgentExtension):
    name = "documents"
    description = "Local Docling conversion, paginated Markdown reading and literal search."
    instructions_file = "instructions.md"
    config = DocumentsConfig

    def load(self):
        if self.loaded:
            return self
        super().load()
        self._temporary = TemporaryDirectory(prefix="harness-documents-") if not self.agent.session_root else None
        self.root = (self.agent.session_root / "documents" if self.agent.session_root
                     else Path(self._temporary.name))
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._lock = asyncio.Lock()
        return self

    def shutdown(self):
        if self._temporary is not None:
            self._temporary.cleanup()

    def _entry(self, document_id):
        if not re.fullmatch(r"[0-9a-f]{24}", document_id):
            raise ValueError("Invalid document_id; use the identifier returned by open_document.")
        entry = self.root / document_id
        if not (entry / "metadata.json").is_file():
            raise FileNotFoundError("Document not cached; call open_document first.")
        return entry

    def _text(self, document_id):
        entry = self._entry(document_id)
        return (entry / "document.md").read_text(encoding="utf-8")

    @staticmethod
    def _snapshot(source, target):
        digest = hashlib.sha256()
        size = 0
        with source.open("rb") as incoming, target.open("xb") as outgoing:
            while block := incoming.read(1024 * 1024):
                size += len(block)
                if size > MAX_FILE_BYTES:
                    raise ValueError("Document exceeds the 100 MiB input limit.")
                digest.update(block)
                outgoing.write(block)
        return digest.hexdigest(), size

    async def _convert(self, source, output, options):
        python = Path(self.config.python).expanduser() if self.config.python else RUNTIME / ".venv/bin/python"
        if not python.is_file():
            raise RuntimeError("Docling runtime missing. Run: uv sync --project the_harness/plugins/documents/runtime --frozen")
        timeout = self.config.timeout_seconds
        if not isinstance(timeout, int) or isinstance(timeout, bool) or not 1 <= timeout <= 900:
            raise ValueError("documents.timeout_seconds must be an integer from 1 to 900.")
        with (output / "conversion.log").open("wb") as log:
            process = await asyncio.create_subprocess_exec(
                str(python), str(RUNTIME / "convert.py"), str(source), str(output), json.dumps(options),
                stdin=asyncio.subprocess.DEVNULL, stdout=log, stderr=log,
                start_new_session=True,
                env={**os.environ, "HF_HUB_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1",
                     "DO_NOT_TRACK": "1", "OMP_NUM_THREADS": "4"},
            )
            try:
                await asyncio.wait_for(process.wait(), timeout=timeout)
            except (asyncio.CancelledError, TimeoutError):
                if process.returncode is None:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    await process.wait()
                raise
        if process.returncode:
            with (output / "conversion.log").open("rb") as log:
                log.seek(max(0, log.seek(0, 2) - 2500))
                detail = log.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Docling conversion failed (exit {process.returncode}): {detail}")

    @tool
    async def open_document(self, path: str, ocr: bool = True, force_ocr: bool = False,
                            page_start: int = 1, page_end: int | None = None):
        """Convert a local PDF, Office file, scan or other Docling document into a persistent cache.

        Returns metadata, a bounded preview, heading offsets and Markdown/JSON paths,
        not the entire document. PDF page bounds are inclusive and one-based; at most
        500 pages per conversion. OCR uses local models, force_ocr also re-reads native
        PDF text. URLs are not accepted. Originals are never modified.
        """
        if not isinstance(page_start, int) or isinstance(page_start, bool) or page_start < 1:
            raise ValueError("page_start must be a positive integer.")
        if page_end is not None and (not isinstance(page_end, int) or isinstance(page_end, bool)
                                     or page_end < page_start):
            raise ValueError("page_end must be an integer >= page_start.")
        if page_end is not None and page_end - page_start >= 500:
            raise ValueError("Select at most 500 pages.")
        if force_ocr and not ocr:
            raise ValueError("force_ocr requires ocr=True.")
        source = Path(path).expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError(f"Not a local document: {path}")
        if source.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("Document exceeds the 100 MiB input limit.")
        options = {"ocr": ocr, "force_ocr": force_ocr, "page_start": page_start, "page_end": page_end}
        # Serialize conversion to cap memory use and publish a cache entry atomically.
        async with self._lock:
            with TemporaryDirectory(prefix=".convert-", dir=self.root) as temporary:
                work = Path(temporary)
                os.chmod(work, 0o700)
                snapshot = work / ("source" + source.suffix.lower())
                digest, size = await asyncio.to_thread(self._snapshot, source, snapshot)
                key = hashlib.sha256()
                for value in (digest, source.suffix.lower(), json.dumps(options, sort_keys=True),
                              (RUNTIME / "uv.lock").read_text(), (RUNTIME / "convert.py").read_text()):
                    key.update(value.encode())
                document_id = key.hexdigest()[:24]
                entry = self.root / document_id
                cached = (entry / "metadata.json").is_file()
                if not cached:
                    await self._convert(snapshot, work, options)
                    metadata = json.loads((work / "metadata.json").read_text())
                    metadata.update(document_id=document_id, sha256=digest, source_bytes=size)
                    (work / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
                    snapshot.unlink()
                    work.rename(entry)
                metadata = json.loads((entry / "metadata.json").read_text())
                text = (entry / "document.md").read_text(encoding="utf-8")
                return {**metadata, "source": str(source), "cached": cached,
                        "markdown_path": str(entry / "document.md"), "json_path": str(entry / "document.json"),
                        "preview": text[:4000], "next_offset": 4000 if len(text) > 4000 else None}

    @tool
    def read_document(self, document_id: str, offset: int = 0, limit: int = 12000):
        """Read cached Markdown by character offset; returns a continuation offset and relevant pages.

        limit is 1..20000 characters. Page markers originate from PDF/image provenance,
        not estimated pagination. Reuse the stable document_id after a restart.
        """
        text = self._text(document_id)
        if not isinstance(offset, int) or isinstance(offset, bool) or not 0 <= offset <= len(text):
            raise ValueError("offset must be between zero and total_chars.")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 20000:
            raise ValueError("limit must be an integer from 1 to 20000.")
        end = min(offset + limit, len(text))
        metadata = json.loads((self._entry(document_id) / "metadata.json").read_text())
        pages = [page for page in metadata["pages"] if page["offset"] < end and page["end_offset"] > offset]
        return {"document_id": document_id, "offset": offset, "total_chars": len(text),
                "text": text[offset:end], "pages": pages, "next_offset": end if end < len(text) else None}

    @tool
    def search_document(self, document_id: str, query: str, offset: int = 0, limit: int = 10):
        """Find literal text, case-insensitively, in cached Markdown, with bounded contexts and offsets.

        query is 1..200 characters; limit is 1..20 matches. next_offset continues
        searching. Offsets can be passed to read_document. No regex or semantic search.
        """
        if not query or len(query) > 200:
            raise ValueError("query must contain 1..200 characters.")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 20:
            raise ValueError("limit must be an integer from 1 to 20.")
        text = self._text(document_id)
        if not isinstance(offset, int) or isinstance(offset, bool) or not 0 <= offset <= len(text):
            raise ValueError("offset must be between zero and total_chars.")
        matches = []
        for match in re.finditer(re.escape(query), text[offset:], re.IGNORECASE):
            start, end = offset + match.start(), offset + match.end()
            if len(matches) == limit:
                return {"document_id": document_id, "matches": matches, "next_offset": start}
            matches.append({"offset": start, "end_offset": end,
                            "context_offset": max(0, start - 150),
                            "context": text[max(0, start - 150):end + 250]})
        return {"document_id": document_id, "matches": matches, "next_offset": None}
