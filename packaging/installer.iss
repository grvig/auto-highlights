; Windows installer for auto-highlights (Inno Setup).
;
;   ISCC.exe /DSourceDir=<dist\auto-highlights> /DOutputDir=<folder> packaging\installer.iss
;
; Installs per user (no admin prompt) into %LOCALAPPDATA%\Programs. ffmpeg and
; HLAE are not inside: the app downloads them on first run (the window's
; readiness page, or --setup), which keeps this installer small and lets HLAE
; update when CS2 changes.

#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\build\dist\auto-highlights"
#endif
#ifndef OutputDir
  #define OutputDir "..\build\installer"
#endif

[Setup]
AppId={{6F7C3B1E-2A44-4C8E-9C61-5B2D7F0A9E13}
AppName=auto-highlights
AppVersion={#AppVersion}
AppPublisher=GR
DefaultDirName={localappdata}\Programs\auto-highlights
DefaultGroupName=auto-highlights
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
OutputDir={#OutputDir}
OutputBaseFilename=auto-highlights-{#AppVersion}-setup
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Icons]
; Started without arguments the exe opens the app window.
Name: "{group}\auto-highlights"; Filename: "{app}\auto-highlights.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\auto-highlights"; Filename: "{app}\auto-highlights.exe"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{group}\Uninstall auto-highlights"; Filename: "{uninstallexe}"

[Run]
; The window checks what is missing and offers to download ffmpeg and HLAE.
Filename: "{app}\auto-highlights.exe"; Description: "Open auto-highlights"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
; settings, downloaded tools and caches; finished reels in Videos are kept
Type: filesandordirs; Name: "{localappdata}\auto-highlights"
