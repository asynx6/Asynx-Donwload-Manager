"""Regenerate frontend/ui/assets/icons/app.ico from root Logo.png using Pillow.

Produces multi-size .ico suitable for Windows Explorer, taskbar, and
window icon. Old app.ico (78 KiB) is preserved as app.ico.bak for
rollback.
"""
from pathlib import Path

import shutil
from PIL import Image


ROOT = Path(r"C:\Users\asynx\Downloads\AsynxDL")
LOGO = ROOT / "Logo.png"
ICO = ROOT / "frontend" / "ui" / "assets" / "icons" / "app.ico"
BAK = ICO.with_suffix(".ico.bak")
LOGO_DEST = ROOT / "frontend" / "ui" / "assets" / "icons" / "logo.png"


def main() -> int:
    if not LOGO.exists():
        print(f"[ERROR] missing {LOGO}")
        return 2

    if ICO.exists():
        if BAK.exists():
            BAK.unlink()
        ICO.rename(BAK)
        print(f"[BACKUP] {ICO.name} -> {BAK.name} ({BAK.stat().st_size:,} B)")
    else:
        print(f"[INFO] no existing {ICO.name}, creating fresh")

    src = Image.open(LOGO).convert("RGBA")
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
             (128, 128), (256, 256)]
    src.save(ICO, format="ICO", sizes=sizes)
    print(f"[OK] {ICO} ({ICO.stat().st_size:,} B, sizes={sizes})")

    try:
        LOGO_DEST.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(LOGO), str(LOGO_DEST))
        print(f"[MIRROR] {LOGO_DEST} ({LOGO_DEST.stat().st_size:,} B)")
    except Exception as exc:
        print(f"[WARN] logo.png mirror failed: {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
