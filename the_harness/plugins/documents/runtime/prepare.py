"""Download only the local models used by the documents plugin (no user files)."""

from docling.utils.model_downloader import download_models

if __name__ == "__main__":
    download_models(
        with_code_formula=False,
        with_picture_classifier=False,
        rapidocr_models=["onnxruntime:latin"],
        progress=True,
    )
