#define MyAppName "AsynxDL"
#define MyAppVersion "1.0.0"  ; masih development
#define MyAppPublisher "AsynxDL"
#define MyAppURL "https://github.com/asynxdl/asynxdl"
#define MyAppExeName "AsynxDL.exe"

[Setup]
AppId={{A8F2C1E7-9B3D-4E5A-8C1F-7D6E9B0A2C3F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\AsynxDL
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
UsePreviousAppDir=no
AppendDefaultDirName=no
OutputDir=..\dist
OutputBaseFilename=AsynxDL_Setup_v{#MyAppVersion}
SetupIconFile=..\frontend\ui\assets\icons\app.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
CloseApplications=no
RestartApplications=no
DefaultGroupName={#MyAppName}
UninstallFilesDir={app}
Uninstallable=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\AsynxDL.exe"; DestDir: "{app}"; Flags: ignoreversion
; v2.0.1: debug variant is opt-in (see build/asynxdl_debug.spec) — not in installer.
; To ship a debug-installer, run pyinstaller on asynxdl_debug.spec and uncomment:
; Source: "..\dist\AsynxDL_Debug.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\extension\browser\*"; DestDir: "{app}\extension\browser"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.id.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\CONTRIBUTING.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[UninstallRun]
Filename: "reg"; Parameters: "delete HKCU\Software\Microsoft\Windows\CurrentVersion\Run /v AsynxDL /f"; Flags: runascurrentuser skipifdoesntexist; RunOnceId: "RemoveAutoRun"

[Code]
function KillAsynxDL(): Boolean;
var
  ResultCode: Integer;
  Timeout: Integer;
  Params: String;
begin
  // First try taskkill by image name (graceful-ish forced kill)
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/f /im AsynxDL.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/f /im AsynxDL_Debug.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

  // Fallback: PowerShell Stop-Process for stubborn/hidden instances
  Params := '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -Command "Get-Process | Where-Object {$_.ProcessName -like ''AsynxDL*''} | Stop-Process -Force -ErrorAction SilentlyContinue"';
  Exec(ExpandConstant('{sys}\windowspowershell\v1.0\powershell.exe'), Params, '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

  // Wait up to ~3 seconds for the process to really exit
  Timeout := 0;
  while (Timeout < 30) do
  begin
    Exec(ExpandConstant('{sys}\taskkill.exe'), '/f /im AsynxDL.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Exec(ExpandConstant('{sys}\taskkill.exe'), '/f /im AsynxDL_Debug.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Sleep(100);
    Timeout := Timeout + 1;
  end;
  Result := True;
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  // KillAsynxDL is intentionally NOT called here because the helper's Exec
  // calls were making the silent installer abort on this machine. Active
  // processes will be killed during uninstall instead.
end;

function InitializeUninstall(): Boolean;
begin
  Result := True;
  KillAsynxDL();
  Sleep(1000);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    KillAsynxDL();
    Sleep(1000);
  end;
end;

[UninstallDelete]
Type: filesandordirs; Name: "{app}\*"
Type: dirifempty; Name: "{app}"
Type: filesandordirs; Name: "{localappdata}\AsynxDL"
Type: filesandordirs; Name: "{userappdata}\AsynxDL"
Type: files; Name: "{autodesktop}\AsynxDL.lnk"
Type: files; Name: "{userstartup}\AsynxDL.lnk"
; Also delete the hidden parts directory
Type: filesandordirs; Name: "{localappdata}\AsynxDL\.parts"
