#ifndef AppVersion
  #error AppVersion must be supplied by tools/build.ps1
#endif
#ifndef AppSource
  #error AppSource must be the audited frozen application directory
#endif

[Setup]
AppId={{61D8364E-DA74-4B18-B7B6-9D231971FFCE}
AppName=Saydraft
AppVersion={#AppVersion}
AppPublisher=Tanzir Rahman
AppPublisherURL=https://tanziro.com
AppSupportURL=https://github.com/tanzir71/saydraft/issues
AppUpdatesURL=https://github.com/tanzir71/saydraft/releases
DefaultDirName={localappdata}\Programs\Saydraft
DefaultGroupName=Saydraft
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputBaseFilename=Saydraft-{#AppVersion}-Setup
LicenseFile=..\LICENSE
SetupIconFile=..\assets\tray\mic_idle.ico
UninstallDisplayIcon={app}\Saydraft.exe
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
AppCopyright=Copyright (c) 2026 Tanzir Rahman

[Tasks]
Name: "autostart"; Description: "Start Saydraft when I sign in"; Flags: unchecked

[Files]
Source: "{#AppSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Saydraft"; Filename: "{app}\Saydraft.exe"

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Saydraft"; ValueData: """{app}\Saydraft.exe"""; Tasks: autostart

[Run]
Filename: "{app}\Saydraft.exe"; Description: "Open Saydraft"; Flags: nowait postinstall skipifsilent

[Code]
var
  RemoveUserData: Boolean;

function InitializeUninstall: Boolean;
var
  ChoiceForm: TSetupForm;
  Description: TNewStaticText;
  RemoveCheck: TNewCheckBox;
  RemoveButton, CancelButton: TNewButton;
begin
  RemoveUserData := False;
  Result := True;
  if UninstallSilent then begin
    { Explicit automation equivalent of checking the box. Default is keep. }
    RemoveUserData := ExpandConstant('{param:REMOVEDATA|0}') = '1';
    Exit;
  end;
#if VER >= EncodeVer(6, 6, 0)
  ChoiceForm := CreateCustomForm(470, 210, False, False);
#else
  ChoiceForm := CreateCustomForm;
  ChoiceForm.ClientWidth := ScaleX(470);
  ChoiceForm.ClientHeight := ScaleY(210);
#endif
  try
    ChoiceForm.Caption := 'Uninstall Saydraft';
    ChoiceForm.Position := poScreenCenter;
    Description := TNewStaticText.Create(ChoiceForm);
    Description.Parent := ChoiceForm;
    Description.SetBounds(ScaleX(20), ScaleY(20), ScaleX(430), ScaleY(68));
    Description.AutoSize := False;
    Description.WordWrap := True;
    Description.Caption := 'Remove Saydraft from this PC? Your settings, History, notes and default model downloads will be kept unless you select the option below.';
    RemoveCheck := TNewCheckBox.Create(ChoiceForm);
    RemoveCheck.Parent := ChoiceForm;
    RemoveCheck.SetBounds(ScaleX(20), ScaleY(96), ScaleX(430), ScaleY(24));
    RemoveCheck.Caption := 'Also remove my Saydraft data';
    RemoveCheck.Checked := False;
    Description := TNewStaticText.Create(ChoiceForm);
    Description.Parent := ChoiceForm;
    Description.SetBounds(ScaleX(20), ScaleY(128), ScaleX(430), ScaleY(32));
    Description.AutoSize := False;
    Description.WordWrap := True;
    Description.Caption := 'Custom model folders and earlier VoiceTray backups are kept.';
    RemoveButton := TNewButton.Create(ChoiceForm);
    RemoveButton.Parent := ChoiceForm;
    RemoveButton.SetBounds(ScaleX(258), ScaleY(172), ScaleX(92), ScaleY(26));
    RemoveButton.Caption := 'Uninstall';
    RemoveButton.ModalResult := mrOk;
    RemoveButton.Default := True;
    CancelButton := TNewButton.Create(ChoiceForm);
    CancelButton.Parent := ChoiceForm;
    CancelButton.SetBounds(ScaleX(360), ScaleY(172), ScaleX(90), ScaleY(26));
    CancelButton.Caption := 'Cancel';
    CancelButton.ModalResult := mrCancel;
    CancelButton.Cancel := True;
    Result := ChoiceForm.ShowModal = mrOk;
    RemoveUserData := Result and RemoveCheck.Checked;
  finally
    ChoiceForm.Free;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Existing, Expected, DataRoot, ParentRoot: String;
begin
  if CurUninstallStep <> usPostUninstall then Exit;
  Expected := '"' + ExpandConstant('{app}\Saydraft.exe') + '"';
  if RegQueryStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', 'Saydraft', Existing) then
    if CompareText(Existing, Expected) = 0 then
      RegDeleteValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', 'Saydraft');
  if not RemoveUserData then Exit;
  ParentRoot := RemoveBackslashUnlessRoot(ExpandConstant('{localappdata}'));
  DataRoot := ParentRoot + '\Saydraft';
  { Check the resolved, explicitly named app directory before recursive deletion.
    Inno DelTree removes reparse points without recursing into their targets. }
  if (CompareText(ExtractFileDir(DataRoot), ParentRoot) <> 0) or
     (CompareText(ExtractFileName(DataRoot), 'Saydraft') <> 0) then
    RaiseException('Saydraft data path could not be verified');
  if DirExists(DataRoot) then
    if not DelTree(DataRoot, True, True, True) then
      Log('Some Saydraft data could not be removed; it remains in the user profile.');
  DeleteFile(ParentRoot + '\Saydraft.migration.json');
end;
