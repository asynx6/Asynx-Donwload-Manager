import sys
import os


def set_startup(enabled: bool):
    """Set/remove Windows registry run key untuk auto-startup.
    Guard: hanya di Windows.
    """
    if sys.platform != "win32":
        return
    try:
        import winreg
    except ImportError:
        return

    REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
    APP_NAME = "AsynxDL"

    # Saat frozen, executable adalah app.exe. Saat development, gunakan __file__.
    if getattr(sys, "frozen", False):
        exe = sys.executable
    else:
        # Gunakan script entry point utama
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        exe = os.path.join(base, "backend", "main.py")

    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_SET_VALUE)
    try:
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{exe}" --minimized')
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
    finally:
        winreg.CloseKey(key)
