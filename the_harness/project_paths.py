"""Application resources in a source checkout or an installed wheel."""
from pathlib import Path


def project_root():
    package = Path(__file__).resolve().parent
    bundled = package / "_project"
    return bundled if bundled.is_dir() else package.parent


PROJECT_ROOT = project_root()
