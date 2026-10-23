# Local document reading

The `documents` plugin converts local files through Docling in a separate Python
3.12 process. It does not import Docling, PyTorch or OCR engines into the agent
worker. Conversion uses CPU inference and disables remote conversion services
and external Docling plugins.

## Setup

From the repository root:

```sh
uv sync --project the_harness/plugins/documents/runtime --frozen
the_harness/plugins/documents/runtime/.venv/bin/python the_harness/plugins/documents/runtime/prepare.py
```

Installation downloads dependencies and local layout, table and Latin OCR models
(approximately 682 MB of model files, plus the Python environment). Conversion
runs with Hugging Face offline mode; missing models cause an error rather than
an automatic model download. No document is uploaded by this plugin. Extracted
passages returned to the agent become part of its normal model context, so local
conversion does not mean that subsequent conversation is entirely offline.

Models normally live in `~/.cache/docling/models`. If relocating them, set
`DOCLING_ARTIFACTS_PATH` in the server environment to the prepared model directory.
Restart the server after installing or changing the plugin. Its agent binding
can be enabled or disabled like other plugins.

## Tools

- `open_document(path, ocr=True, force_ocr=False, page_start=1, page_end=None)`:
  convert or reuse an immutable cache entry; return a document ID, short preview,
  headings, page offsets, warnings and Markdown/structured JSON paths.
- `read_document(document_id, offset=0, limit=12000)`: read a bounded passage;
  follow `next_offset` until it is null.
- `search_document(document_id, query, offset=0, limit=10)`: case-insensitive
  literal search with surrounding context and continuation offsets.

Offsets count Unicode characters, not bytes. PDF page bounds are inclusive and
one-based. Reflowable Office files need not have page numbers. The original is
never modified. Source bytes, format, options and converter implementation
identify a cache entry; cached exports persist under the session's private
`documents/` directory, not the public bucket. They contain extracted document
content and should be treated as private data.

Verified with synthetic fixtures: native two-page PDF, DOCX with a table and
accents, XLSX, PPTX, HTML, scanned PNG and scanned PDF, plus page selection,
cache reuse and invalid PDF rejection. Docling also supports additional formats,
but they are not covered by these smoke tests. Legacy `.doc`/`.xls`/`.ppt` and
RTF may need a separately installed LibreOffice. OCR and complex tables can
contain errors; inspect the source when accuracy matters.

## Bounds and configuration

Conversions are serialized per extension and limited to 100 MiB input, 500 pages
and 20 million extracted characters. A subprocess is terminated on cancellation
or timeout. `documents.timeout_seconds` defaults to 300 (range 1–900); Docling's
PDF pipeline has its own 270-second timeout. `documents.python` optionally selects
another compatible Python environment. No memory sandbox is provided; large or
complex documents can still use substantial CPU/RAM. Output previews and reads
are bounded rather than injecting an entire document into context.

## Verification

```sh
uv run pytest -q tests/general/test_documents_plugin.py
HARNESS_DOCUMENTS_LIVE=1 uv run pytest -q -s tests/agentic/test_documents_live.py
```

The opt-in test requires the prepared runtime and models. It generates only
synthetic documents and does not use personal files.
