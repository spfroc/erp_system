"""Pack ERP release for huawei_52 including notice_crawler. No secrets/media."""

from __future__ import annotations

import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path.home() / "AppData" / "Local" / "Temp" / "yzc-erp-huawei.tgz"
INCLUDE = ("backend", "frontend", "official-web", "deploy", "notice_crawler", "ocr-service")
SKIP_DIRS = {
    "node_modules",
    "dist",
    "__pycache__",
    ".pytest_cache",
    "media",
    ".git",
    "data",
    "models",
    "venv",
    ".venv",
}
SKIP_FILES = {".env", ".env.prod", ".env.local", ".env.official"}


def allow(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if any(part in SKIP_DIRS for part in rel.parts):
        return False
    if path.name in SKIP_FILES or path.suffix == ".pyc":
        return False
    return True


def main() -> None:
    with tarfile.open(OUT, "w:gz") as archive:
        for name in INCLUDE:
            base = ROOT / name
            if not base.exists():
                raise SystemExit(f"missing {base}")
            for path in base.rglob("*"):
                if not path.is_file() or not allow(path):
                    continue
                archive.add(path, arcname=path.relative_to(ROOT).as_posix())
    print(OUT)
    print(OUT.stat().st_size)


if __name__ == "__main__":
    main()
