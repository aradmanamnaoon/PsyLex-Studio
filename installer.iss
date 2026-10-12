#define MyAppName "PsyLex Studio"
#define MyAppVersion "0.6.5"
#define MyAppExeName "PsyLexStudio.exe"
[Setup]
AppId={{02D246A9-82DD-4E16-BF10-9180F69E822F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=PsyLex Contributors
DefaultDirName={localappdata}\Programs\PsyLex Studio
DefaultGroupName=PsyLex Studio
OutputDir=dist\installer
OutputBaseFilename=PsyLexStudio-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
Source: "dist\PsyLexStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch PsyLex Studio"; Flags: nowait postinstall skipifsilent
