"""Document reading stays bounded, cached, private and cancellable."""

import asyncio
import json
import os
from pathlib import Path
import sys
from types import MethodType

import pytest

from the_framework.agent import Agent
from the_harness.plugins.documents.agent import DocumentsExtension, RUNTIME


def setup(tmp_path):
    agent = Agent(client=object(), session_path=tmp_path / "session.json")
    return agent, agent.add_extension(DocumentsExtension)


def write_conversion(output, text="## Titre\n\nCafé et école.\n" * 300):
    (output / "document.md").write_text(text, encoding="utf-8")
    (output / "document.json").write_text("{}")
    (output / "metadata.json").write_text(json.dumps({
        "pages": [{"page": 1, "offset": 0, "end_offset": len(text)}],
        "outline": [], "total_chars": len(text), "status": "success", "warnings": [],
    }))


def fake_conversion(plugin, calls):
    async def convert(self, source, output, options):
        calls.append((source.read_bytes(), options))
        write_conversion(output)
    plugin._convert = MethodType(convert, plugin)


def test_tools_and_instructions_can_be_disabled(tmp_path):
    agent, plugin = setup(tmp_path)
    assert "documents" in agent.registry("tools")
    assert "documents" in agent.registry("instructions")
    plugin.deactivate()
    assert "documents" not in agent.registry("tools")


def test_open_cache_and_restart_keep_immutable_snapshots(tmp_path):
    source = tmp_path / "test.docx"
    source.write_bytes(b"document version 1")
    _, plugin = setup(tmp_path)
    calls = []
    fake_conversion(plugin, calls)
    opened = asyncio.run(plugin.open_document(str(source)))
    assert len(opened["preview"]) == opened["next_offset"] == 4000
    assert not opened["cached"] and len(calls) == 1
    assert Path(opened["json_path"]).is_file()
    assert not list(plugin.root.glob(".convert-*"))
    assert not (plugin.root / opened["document_id"] / "source.docx").exists()
    assert os.stat(plugin.root / opened["document_id"]).st_mode & 0o777 == 0o700
    again = asyncio.run(plugin.open_document(str(source)))
    assert again["cached"] and again["document_id"] == opened["document_id"]
    assert len(calls) == 1
    _, restored = setup(tmp_path)
    assert restored.read_document(opened["document_id"], 5, 3)["text"] == "tre"
    source.write_bytes(b"document version 2")
    changed = asyncio.run(plugin.open_document(str(source)))
    assert changed["document_id"] != opened["document_id"]
    assert len(calls) == 2
    assert source.read_bytes() == b"document version 2"


def test_read_and_search_offsets_are_bounded_and_unicode_correct(tmp_path):
    _, plugin = setup(tmp_path)
    entry = plugin.root / ("a" * 24)
    entry.mkdir()
    text = "İ et Café — café — école — CAFÉ"
    write_conversion(entry, text)
    result = plugin.search_document(entry.name, "café", limit=2)
    assert [match["offset"] for match in result["matches"]] == [5, 12]
    assert plugin.search_document(entry.name, "café", result["next_offset"])["matches"][0]["offset"] == 27
    part = plugin.read_document(entry.name, 5, 4)
    assert part["text"] == "Café" and part["next_offset"] == 9
    assert part["pages"][0]["page"] == 1
    for offset, limit in [(-1, 1), (0, 20001), (0, 0), (len(text) + 1, 1)]:
        with pytest.raises(ValueError):
            plugin.read_document(entry.name, offset, limit)
    assert plugin.search_document(entry.name, "[")["matches"] == []
    with pytest.raises(ValueError):
        plugin.read_document("../../secret")


def test_bad_options_missing_input_and_failed_conversion_do_not_publish(tmp_path):
    _, plugin = setup(tmp_path)
    source = tmp_path / "test.pdf"
    source.write_bytes(b"invalid PDF")
    async def broken(self, source, output, options):
        raise RuntimeError("invalid PDF")
    plugin._convert = MethodType(broken, plugin)
    for options in [{"page_start": 0}, {"page_end": 501}, {"page_start": 3, "page_end": 2},
                    {"ocr": False, "force_ocr": True}]:
        with pytest.raises(ValueError):
            asyncio.run(plugin.open_document(str(source), **options))
    with pytest.raises(FileNotFoundError):
        asyncio.run(plugin.open_document("https://example.org/private.pdf"))
    with pytest.raises(RuntimeError, match="invalid PDF"):
        asyncio.run(plugin.open_document(str(source)))
    assert list(plugin.root.iterdir()) == []


@pytest.mark.parametrize("cancel", [False, True])
def test_conversion_timeout_and_cancellation_reap_child(tmp_path, monkeypatch, cancel):
    _, plugin = setup(tmp_path)
    plugin.config.python = sys.executable
    plugin.config.timeout_seconds = 1
    fixture = tmp_path / "runtime"
    fixture.mkdir()
    pidfile = tmp_path / "child.pid"
    (fixture / "convert.py").write_text(
        f"import os,time\nfrom pathlib import Path\nPath({str(pidfile)!r}).write_text(str(os.getpid()))\ntime.sleep(30)\n"
    )
    monkeypatch.setattr("the_harness.plugins.documents.agent.RUNTIME", fixture)
    output = tmp_path / "conversion"
    output.mkdir()
    async def run():
        task = asyncio.create_task(plugin._convert(tmp_path / "source.pdf", output, {}))
        for _ in range(100):
            if pidfile.exists():
                break
            await asyncio.sleep(0.01)
        assert pidfile.exists()
        if cancel:
            task.cancel()
        with pytest.raises(asyncio.CancelledError if cancel else TimeoutError):
            await task
    asyncio.run(run())
    with pytest.raises(ProcessLookupError):
        os.kill(int(pidfile.read_text()), 0)


def test_runtime_is_separate_and_importing_plugin_does_not_import_docling():
    assert (RUNTIME / "uv.lock").is_file()
    assert "docling" not in sys.modules
