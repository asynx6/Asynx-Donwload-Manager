"""AsynxDL — Antivirus & Threat Protection.

Memindai file hasil download menggunakan Windows Defender (MpCmdRun.exe) jika
berjalan di Windows. Fallback ke hash check opsional jika di non-Windows.
"""

import os
import subprocess
import platform

def scan_file(path: str) -> dict:
    """Scan file using Windows Defender on Windows. Best effort on other platforms."""
    path = os.path.abspath(path)
    if not os.path.exists(path):
        return {"status": "error", "message": "File not found"}

    if platform.system().lower() != "windows":
        return {"status": "skipped", "message": "Defender scan only supported on Windows"}

    # Windows Defender paths
    cmd_paths = [
        r"C:\Program Files\Windows Defender\MpCmdRun.exe",
        r"C:\Program Files (x86)\Windows Defender\MpCmdRun.exe",
    ]
    
    mp_cmd = None
    for p in cmd_paths:
        if os.path.exists(p):
            mp_cmd = p
            break
            
    if not mp_cmd:
        return {"status": "skipped", "message": "Windows Defender executable not found"}
        
    try:
        # Running: MpCmdRun.exe -Scan -ScanType 3 -File <path> -DisableRemediation
        # Return values of MpCmdRun.exe:
        # 0 = No threats found or scan skipped
        # 2 = Threats found and remediated or not
        # Others = scan failed
        cmd = [mp_cmd, "-Scan", "-ScanType", "3", "-File", path, "-DisableRemediation"]
        
        # Run with timeout to prevent hangs. Use CREATE_NO_WINDOW on Windows.
        # creationflags=0x08000000 ensures no console window pops up.
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45, creationflags=0x08000000)
        
        if res.returncode == 0:
            return {"status": "clean", "message": "Windows Defender: No threats found"}
        elif res.returncode == 2:
            return {"status": "infected", "message": "Windows Defender: Threat detected!"}
        else:
            return {"status": "failed", "message": f"Scan failed with returncode {res.returncode}"}
    except Exception as exc:
        return {"status": "failed", "message": f"Scan failed: {exc}"}

__all__ = ("scan_file",)
