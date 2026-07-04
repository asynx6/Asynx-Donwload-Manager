import sys
import time as _t
import shutil as _s
from pathlib import Path as _P


def cleanup_dist(backup: bool = True) -> bool:
    """Hapus dist/ + build/{asynxdl,asynxdl_debug}.

    Backup disinkronkan ke sibling `dist.bak-<timestamp>/` (di parent, sibling
    bukan anak sehingga Windows tidak melakukan nested-rename). Backup opsional,
    return True kalau dist selesai dibersihkan.
    """
    ROOT = _P(__file__).resolve().parent
    DIST = ROOT / "dist"
    BUILDS = [
        ROOT / "build" / "asynxdl",
        ROOT / "build" / "asynxdl_debug",
    ]
    if backup and DIST.exists():
        ts = _t.strftime("%Y%m%d-%H%M%S")
        bak = DIST.parent / f"dist.bak-{ts}"
        try:
            if bak.exists():
                _s.rmtree(bak, ignore_errors=True)
            _s.move(str(DIST), str(bak))
            print(f"[BACKUP] {DIST} -> {bak}")
        except OSError as exc:
            print(f"[WARN] backup failed (continuing): {exc}")
    for d in BUILDS:
        if d.exists():
            try:
                _s.rmtree(d, ignore_errors=True)
                print(f"[CLEAN] {d}")
            except Exception:
                pass
    # recreate empty dist
    try:
        DIST.mkdir(exist_ok=True)
        print(f"[READY] empty {DIST}")
    except Exception:
        pass
    return True


if __name__ == "__main__":
    backup = True
    for arg in sys.argv[1:]:
        if arg in ("--no-backup", "-nb"):
            backup = False
    cleanup_dist(backup=backup)
