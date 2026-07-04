"""List final build artifacts in dist/ for AsynxDL v1.0.0-dev release."""
import os
from pathlib import Path


dist = Path(r"C:\Users\asynx\Downloads\AsynxDL\dist")
if not dist.exists():
    print(f"[MISSING] {dist}")
    raise SystemExit(1)

items = sorted(dist.iterdir())
print(f"[DIST] {dist}")
free_label = "n/a"
try:
    import shutil
    free_label = f"{shutil.disk_usage(dist).free / 1024**3:.1f} GiB free"
except Exception:
    pass
print(f"  free disk: {free_label}")
for it in items:
    if it.is_file():
        size_mib = it.stat().st_size / 1024 / 1024
        size_kib = it.stat().st_size / 1024
        if size_mib >= 1.0:
            print(f"  [F] {it.name}  {size_mib:7.1f} MiB   ({it.stat().st_size:,} B)")
        else:
            print(f"  [F] {it.name}  {size_kib:7.1f} KiB   ({it.stat().st_size:,} B)")
    elif it.is_dir():
        children = list(it.iterdir()) if it.exists() else []
        print(f"  [D] {it.name}{os.sep}  ({len(children)} children)")
print()

EXPECTED = (
    "AsynxDL_Setup_v1.0.0.exe",
    "AsynxDL.exe",
    "AsynxDL_Debug.exe",
    "AsynxDL_Extension.zip",
)
for name in EXPECTED:
    p = dist / name
    print(f"  EXISTS|{name}: {p.exists()}")
