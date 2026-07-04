@echo off
REM Build script untuk AsynxDL
REM Hasil: dist\AsynxDL.exe, dist\AsynxDL_Extension.zip, dist\AsynxDL_Setup_v1.0.1.exe

setlocal enabledelayedexpansion

cd /d "%~dp0\.."

echo [INFO] Membersihkan build lama...
if exist "dist" rmdir /s /q "dist" 2>nul
if exist "build\asynxdl" rmdir /s /q "build\asynxdl" 2>nul

echo [INFO] Building executable (PyInstaller)...
python -m PyInstaller build\asynxdl.spec --clean --noconfirm
if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller gagal.
    exit /b %errorlevel%
)

echo [INFO] Menyalin extension browser ke dist...
if not exist "dist\extension\browser" mkdir "dist\extension\browser"
xcopy /e /i /y "extension\browser\*" "dist\extension\browser\" >nul

echo [INFO] Packaging extension zip...
powershell -NoProfile -Command "Compress-Archive -Path 'extension\browser\*' -DestinationPath 'dist\AsynxDL_Extension.zip' -Force"

echo [INFO] Building installer (Inno Setup)...
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" build\installer.iss
) else (
    echo [WARNING] Inno Setup tidak ditemukan. Install dari https://jrsoftware.org/isdl.php
)

echo [SUCCESS] Build selesai.
echo   - Portable   : dist\AsynxDL.exe
if exist "dist\AsynxDL_Setup_v1.0.1.exe" (
    echo   - Installer  : dist\AsynxDL_Setup_v1.0.1.exe
)
if exist "dist\AsynxDL_Extension.zip" (
    echo   - Extension  : dist\AsynxDL_Extension.zip
)
pause
