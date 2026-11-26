; Inno Setup script. Build:  ISCC packaging\SubGrab.iss   (optionally /DAppVersion=1.2.3)
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{6B3E1C7A-4D2F-4B8E-9F0A-5C1D7E2A9B31}
AppName=SubGrab
AppVersion={#AppVersion}
AppPublisher=SubGrab
DefaultDirName={autopf}\SubGrab
DefaultGroupName=SubGrab
DisableProgramGroupPage=yes
OutputDir=..\installer
OutputBaseFilename=SubGrab-Setup
SetupIconFile=..\assets\subgrab.ico
UninstallDisplayIcon={app}\SubGrab.exe
LicenseFile=..\LICENSE
WizardImageFile=..\assets\installer_wizard.bmp
WizardSmallImageFile=..\assets\installer_small.bmp
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
DisableDirPage=no
PrivilegesRequiredOverridesAllowed=dialog
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
Name: "contextmenu"; Description: "Add ""Download subtitles with SubGrab"" to the folder right-click menu"

[Files]
Source: "..\dist\SubGrab\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\SubGrab"; Filename: "{app}\SubGrab.exe"
Name: "{autodesktop}\SubGrab"; Filename: "{app}\SubGrab.exe"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Software\Classes\Directory\shell\SubGrab"; ValueType: string; ValueName: ""; ValueData: "Download subtitles with SubGrab"; Tasks: contextmenu; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Directory\shell\SubGrab"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\SubGrab.exe"; Tasks: contextmenu
Root: HKA; Subkey: "Software\Classes\Directory\shell\SubGrab\command"; ValueType: string; ValueName: ""; ValueData: """{app}\SubGrab.exe"" ""%1"""; Tasks: contextmenu
Root: HKA; Subkey: "Software\Classes\Directory\Background\shell\SubGrab"; ValueType: string; ValueName: ""; ValueData: "Download subtitles here with SubGrab"; Tasks: contextmenu; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Directory\Background\shell\SubGrab"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\SubGrab.exe"; Tasks: contextmenu
Root: HKA; Subkey: "Software\Classes\Directory\Background\shell\SubGrab\command"; ValueType: string; ValueName: ""; ValueData: """{app}\SubGrab.exe"" ""%V"""; Tasks: contextmenu

[Run]
Filename: "{app}\SubGrab.exe"; Description: "Launch SubGrab"; Flags: nowait postinstall skipifsilent
