"""One-shot Docling worker; imports stay out of the conversational process."""

import json
import os
from pathlib import Path
import re
import sys


def convert(source, output, options):
    from docling.datamodel.base_models import ConversionStatus, InputFormat
    from docling.datamodel.settings import settings
    from docling.datamodel.pipeline_options import AcceleratorOptions, PdfPipelineOptions, RapidOcrOptions
    from docling.document_converter import DocumentConverter, ImageFormatOption, PdfFormatOption

    pipeline = PdfPipelineOptions(
        artifacts_path=Path(os.environ.get("DOCLING_ARTIFACTS_PATH") or settings.cache_dir / "models"),
        enable_remote_services=False,
        allow_external_plugins=False,
        do_ocr=options["ocr"],
        ocr_options=RapidOcrOptions(backend="onnxruntime", lang=["latin"], force_full_page_ocr=options["force_ocr"]),
        accelerator_options=AcceleratorOptions(device="cpu", num_threads=4),
        document_timeout=270,
    )
    converter = DocumentConverter(format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline),
        InputFormat.IMAGE: ImageFormatOption(pipeline_options=pipeline),
    })
    result = converter.convert(
        source, raises_on_error=True, max_num_pages=500, max_file_size=100 * 1024 * 1024,
        page_range=(options["page_start"], options["page_end"] or sys.maxsize),
    )
    if result.status not in {ConversionStatus.SUCCESS, ConversionStatus.PARTIAL_SUCCESS}:
        raise RuntimeError(f"Conversion status: {result.status}")
    document = result.document
    pages = []
    parts = []
    position = 0
    # Only fixed-layout sources have real page numbers. Keep them explicit.
    for number in sorted(document.pages):
        part = f"<!-- page: {number} -->\n\n" + document.export_to_markdown(page_no=number) + "\n\n"
        pages.append({"page": number, "offset": position, "end_offset": position + len(part)})
        position += len(part)
        parts.append(part)
    markdown = "".join(parts) if pages else document.export_to_markdown()
    if len(markdown) > 20_000_000:
        raise ValueError("Converted text exceeds 20 million characters; select a smaller page range.")
    headings = [{"title": match.group(2)[:200], "level": len(match.group(1)), "offset": match.start()}
                for match in re.finditer(r"^(#{1,6}) (.+)$", markdown, re.MULTILINE)]
    metadata = {
        "engine": "docling", "status": result.status.value, "total_chars": len(markdown),
        "pages": pages, "outline": headings[:80], "outline_truncated": len(headings) > 80,
        "options": options, "warnings": [str(error.error_message)[:500] for error in result.errors[:10]],
    }
    if not markdown.strip():
        metadata["warnings"].append("No readable text extracted; try force_ocr or inspect the original.")
    (output / "document.md").write_text(markdown, encoding="utf-8")
    document.save_as_json(output / "document.json")
    (output / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    convert(Path(sys.argv[1]), Path(sys.argv[2]), json.loads(sys.argv[3]))
