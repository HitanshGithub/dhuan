"""Assemble backend/.build/lambda for `sam deploy`: the dhuan package, its Linux wheels, and the district raster.

Usage: uv run python scripts/build_lambda.py

Adapted from the deploy skeleton of my earlier ClaimBack project (MIT): installs manylinux wheels with uv so no Docker is
needed, leaves out boto3 (the Lambda runtime ships it), and keeps *.dist-info because some packages read their own
metadata at import time.
"""

import shutil
import subprocess
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
OUT = BACKEND / ".build" / "lambda"
RUNTIME_PROVIDED = {"boto3", "botocore", "s3transfer", "jmespath", "python-dateutil", "six", "urllib3"}


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    shutil.copytree(BACKEND / "dhuan", OUT / "dhuan", ignore=shutil.ignore_patterns("__pycache__"))
    (OUT / "data").mkdir()
    for name in ("districts.json", "districts_grid.npy"):
        shutil.copy(ROOT / "data" / name, OUT / "data" / name)
    requirements = subprocess.run(
        ["uv", "export", "--no-dev", "--no-hashes", "--no-emit-project", "--format", "requirements-txt"],
        cwd=BACKEND, capture_output=True, text=True, check=True,
    ).stdout
    keep = [line for line in requirements.splitlines() if line.split("==")[0].strip().lower() not in RUNTIME_PROVIDED]
    (OUT / "requirements.txt").write_text("\n".join(keep) + "\n", encoding="utf-8")
    subprocess.run(
        ["uv", "pip", "install", "--target", str(OUT), "--requirement", str(OUT / "requirements.txt"),
         "--python-platform", "x86_64-manylinux_2_28", "--python-version", "3.13", "--quiet"],
        cwd=BACKEND, check=True,
    )
    for junk in OUT.rglob("__pycache__"):
        shutil.rmtree(junk, ignore_errors=True)
    size = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    print(f"built {OUT} ({size / 1e6:.1f} MB with dependencies)")


if __name__ == "__main__":
    main()
