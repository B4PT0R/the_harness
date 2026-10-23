"""Opt-in real Docling checks: HARNESS_DOCUMENTS_LIVE=1 uv run pytest -q -s ..."""

import asyncio
import os
from pathlib import Path
import subprocess
import time

import pytest

from the_framework.agent import Agent
from the_harness.plugins.documents.agent import DocumentsExtension, RUNTIME

pytestmark = pytest.mark.skipif(os.environ.get("HARNESS_DOCUMENTS_LIVE") != "1",
                                reason="opt-in isolated Docling runtime and local models")


def test_real_formats_ocr_page_ranges_cache_and_bad_input(tmp_path):
    root = tmp_path / "sources"
    subprocess.run([str(RUNTIME / ".venv/bin/python"), "tests/fixtures/documents.py", str(root)], check=True)
    agent = Agent(client=object(), session_path=tmp_path / "session.json")
    plugin = agent.add_extension(DocumentsExtension)
    expected = {"native.pdf": ["ATLAS", "BOREAL"], "office.docx": ["ORION", "École", "Stylo", "3,50"],
                "table.xlsx": ["VEGA", "17"], "slides.pptx": ["ALTAIR", "café"],
                "page.html": ["SIRIUS", "École"], "scan.png": ["AZUR", "7319", "42"],
                "scan.pdf": ["AZUR", "7319", "42"]}
    async def run():
        for filename, needles in expected.items():
            start = time.monotonic()
            result = await plugin.open_document(str(root / filename))
            text = Path(result["markdown_path"]).read_text()
            assert result["status"] == "success", result
            for needle in needles:
                assert needle in text, (filename, needle, text)
            print(f"{filename}: {time.monotonic() - start:.2f}s, {len(text)} chars")
            cached = await plugin.open_document(str(root / filename))
            assert cached["cached"] and cached["document_id"] == result["document_id"]
            assert plugin.search_document(result["document_id"], needles[0])["matches"]
        selected = await plugin.open_document(str(root / "native.pdf"), page_start=2, page_end=2)
        text = Path(selected["markdown_path"]).read_text()
        assert "BOREAL" in text and "ATLAS" not in text
        assert [page["page"] for page in selected["pages"]] == [2]
        with pytest.raises(RuntimeError, match="conversion failed"):
            await plugin.open_document(str(root / "broken.pdf"))
    asyncio.run(run())
