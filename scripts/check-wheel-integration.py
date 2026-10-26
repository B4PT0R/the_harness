#!/usr/bin/env python3
"""Verify sibling candidates as installed wheels, never through editable imports."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
# Durable offline contracts; browser and live-service checks remain separate.
CASES = {
    "the_framework": (
        "test_atomic_persistence.py", "test_persistence_commit.py", "test_session.py",
        "test_framework_worker_integration.py",
    ),
    "the_harness": (
        "test_pynteract_plugin.py", "test_remote_ingress.py", "test_selective_reset.py",
    ),
}


def main():
    uv = shutil.which("uv")
    if not uv:
        raise SystemExit("uv is required")
    repos = {name: ROOT.parent / name for name in ("modict", "pynteract", *CASES)}
    for repo in repos.values():
        if not (repo / "pyproject.toml").is_file():
            raise SystemExit(f"Missing sibling checkout: {repo}")
    # Keep Unix socket addresses short, independently of checkout/CI workspace paths.
    work = Path(tempfile.mkdtemp(prefix="hw-", dir="/tmp"))
    print(f"Integration workspace (retained, including on failure): {work}", flush=True)
    env = {key: value for key, value in os.environ.items()
           if key not in {"PYTHONPATH", "VIRTUAL_ENV", "PYTEST_ADDOPTS", "PYTHONHOME"}}
    env.update(PYNTERACT_CONFIG_DIR=str(work / "pynteract-config"),
               XDG_CONFIG_HOME=str(work / "config"), XDG_DATA_HOME=str(work / "data"))

    def run(*args, cwd=work):
        subprocess.run([str(arg) for arg in args], cwd=cwd, env=env, check=True, timeout=600)

    wheels = work / "wheels"
    for repo in repos.values():
        run(uv, "build", "--wheel", "--out-dir", wheels, repo)
    run(uv, "venv", "--python", "3.12", work / "venv")
    python = work / "venv/bin/python"
    # The SDK is intentionally a released dependency; other four wheels are local candidates.
    run(uv, "pip", "install", "--python", python, *sorted(wheels.glob("*.whl")),
        "codex-backend-sdk==0.5.9", "pytest", "pytest-asyncio", "httpx2>=2.0.0")
    run(uv, "pip", "check", "--python", python)
    run(python, "-c", """
import importlib, importlib.metadata, sys
from pathlib import Path
for name, package in [('modict', 'modict'), ('pynteract', 'pynteract'),
                      ('b4pt0r-the-framework', 'the_framework'), ('the-harness', 'the_harness'),
                      ('codex-backend-sdk', 'codex_backend_sdk')]:
    module = importlib.import_module(package)
    path = Path(module.__file__).resolve()
    assert path.is_relative_to(Path(sys.prefix)), path
    print(name, importlib.metadata.version(name), path)
""")
    run(python, "-m", "the_framework", "bootstrap", "--no-prepare",
        "--code-dir", work / "code", "--data-dir", work / "starter-data")
    env["PYTHONPATH"] = str(work / "code")
    for name, cases in CASES.items():
        suite = work / name / "tests"
        suite.mkdir(parents=True)
        for case in cases:
            shutil.copy2(repos[name] / "tests/general" / case, suite / case)
        if name == "the_harness":
            # Reuse the production suite's quota-backend prohibition and fixture imports.
            shutil.copy2(ROOT / "tests/conftest.py", suite / "conftest.py")
            shutil.copy2(ROOT / "tests/__init__.py", suite / "__init__.py")
            shutil.copytree(ROOT / "tests/fixtures", suite / "fixtures", ignore=shutil.ignore_patterns("__pycache__"))
        run(python, "-m", "pytest", "-q", "-ra", "--basetemp", work / f"tmp-{name}",
            "--junitxml", work / f"{name}.xml", suite, cwd=suite.parent)
    print("Wheel installation, worker restart, persistence and Python plugin contracts passed.", flush=True)


if __name__ == "__main__":
    main()
