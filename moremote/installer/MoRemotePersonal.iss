; Inno Setup script for Mo Remote Personal.
; Build the app first (scripts\build.ps1 -> .\dist), then compile this with Inno Setup (ISCC.exe):
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\MoRemotePersonal.iss
; Produces installer\Output\MoRemotePersonal-Setup.exe  (no admin required, per-user install).

#define AppName "Mo Remote Personal"
#define AppVersion "1.0.0"
#define AppExe "MoRemotePersonal.exe"

[Setup]
AppId={{8E0F7A12-BFB3-4FE8-B9A5-48FD50A15A9A}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Mo Remote Personal
DefaultDirName={localappdata}\MoRemotePersonal\app
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=MoRemotePersonal-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\agent\app.ico
UninstallDisplayIcon={app}\{#AppExe}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "startup"; Description: "Start automatically when Windows starts"; GroupDescription: "Startup"; Flags: checkedonce

[Files]
; Copies the entire published self-contained app.
Source: "..\dist\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: startup

[Registry]
; Start-with-Windows (per-user Run key) when the task is selected.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; \
  ValueName: "MoRemotePersonal"; ValueData: """{app}\{#AppExe}"""; Tasks: startup; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch Mo Remote Personal now"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
