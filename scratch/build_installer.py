"""One-off helper to build Inno Setup installer with safe path quoting."""
import os
import subprocess
import sys

from pathlib import Path

project_root = Path(__file__).parent.parent
ISCC_DEFAULT = r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
ISS_FILE = os.path.abspath("build/installer.iss")

iscc = os.environ.get("ISCC_EXE") or ISCC_DEFAULT
if not os.path.exists(iscc):
    # Try the 64-bit Program Files location as a fallback.
    out = project_root / "dist" / "AsynxDL_Setup_v1.0.0.exe"
    alt = r"C:\Program Files\Inno Setup 6\ISCC.exe"
    if os.path.exists(alt):
        iscc = alt

print(f"[build_installer] ISCC = {iscc}")
print(f"[build_installer] ISS  = {ISS_FILE}")
print(f"[build_installer] ISCC exists? = {os.path.exists(iscc)}")
print(f"[build_installer] ISS  exists? = {os.path.exists(ISS_FILE)}")

if not os.path.exists(iscc):
    print("ERROR: ISCC.exe not found. Set ISCC_EXE env or update ISCC_DEFAULT.",
          file=sys.stderr)
    sys.exit(2)

result = subprocess.run([iscc, ISS_FILE], shell=False, capture_output=True, text=True)
print("RC =", result.returncode)
print("STDOUT:\n" + result.stdout[-3000:])
print("STDERR:\n" + result.stderr[-3000:])
sys.exit(result.returncode)
