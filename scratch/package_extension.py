"""Zip extension/browser/* into dist/AsynxDL_Extension.zip for browser integration."""
import shutil
from pathlib import Path


ROOT = Path(r"C:\Users\asynx\Downloads\AsynxDL")
SRC = ROOT / "extension" / "browser"
OUT = ROOT / "dist" / "AsynxDL_Extension.zip"


def main() -> int:
    if not SRC.exists():
        print(f"[ERROR] missing {SRC}")
        return 2

    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()

    archive_base = str(OUT.with_suffix(""))
    shutil.make_archive(archive_base, "zip", root_dir=str(SRC))
    size_kib = OUT.stat().st_size / 1024
    print(f"[OK] {OUT} ({size_kib:.1f} KiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
