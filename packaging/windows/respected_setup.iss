#ifndef MyAppVersion
  #define MyAppVersion "0.0.1"
#endif
#ifndef MyAppId
  #define MyAppId "{870D0E4C-87A0-4A3C-9A82-F8E3C3A19C1D}"
#endif
#ifndef PayloadDir
  #define PayloadDir "..\..\dist\RespectedBrain"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\dist"
#endif

[Setup]
AppId={{#MyAppId}
AppName=Respected Brain
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\RespectedBrain
UsePreviousAppDir=no
PrivilegesRequired=lowest
UninstallFilesDir={app}\uninstall
UninstallLogMode=overwrite
CreateUninstallRegKey=no
OutputDir={#OutputDir}
OutputBaseFilename=RespectedBrain-Windows-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
CloseApplications=no
RestartApplications=no

[Files]
; uninsneveruninstall is forbidden for {tmp}; Inno owns no AppRoot payload.
; Common transaction/ownership manifest performs all product file deletion.
Source: "{#PayloadDir}\*"; DestDir: "{tmp}\payload"; Flags: ignoreversion recursesubdirs createallsubdirs deleteafterinstall

[Code]
var
  VaultPage: TInputDirWizardPage;
  Prepared: Boolean;

function VaultDir: String;
begin
  Result := ExpandConstant('{param:VAULT|{userdocs}\RespectedOS}');
  if not WizardSilent then Result := VaultPage.Values[0];
end;

function DataDir: String;
begin
  Result := ExpandConstant('{param:DATA|{localappdata}\RespectedBrain}');
end;

function RootArgs: String;
begin
  Result := ' --app-root "' + ExpandConstant('{app}') + '" --data-root "' + DataDir + '" --vault "' + VaultDir + '"';
end;

procedure InitializeWizard;
begin
  VaultPage := CreateInputDirPage(wpSelectDir, 'Not kasası', 'Programdan ayrı not klasörünüz', 'Mevcut notlar yerinde korunur. Program ve ayarlar kendi klasörlerine kurulur.', False, '');
  VaultPage.Add('Not kasasının konumu:');
  VaultPage.Values[0] := ExpandConstant('{userdocs}\RespectedOS');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var Code: Integer;
begin
  Result := '';
  if Prepared then Exit;
  ExtractTemporaryFiles('{tmp}\payload\*');
  if not Exec(ExpandConstant('{tmp}\payload\respectedbrain.exe'), '_inno-prepare' + RootArgs + ' --request "' + ExpandConstant('{tmp}\before.json') + '" --registry-key "HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppId}_is1"', '', SW_HIDE, ewWaitUntilTerminated, Code) or (Code <> 0) then
    Result := 'Kurulum ön denetimi başarısız. Program ve not klasörlerini kontrol edin.'
  else Prepared := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var Code: Integer;
begin
  if CurStep = ssPostInstall then begin
    if not Exec(ExpandConstant('{tmp}\payload\respectedbrain.exe'), '_inno-deploy' + RootArgs + ' --package "' + ExpandConstant('{tmp}\payload') + '" --request "' + ExpandConstant('{tmp}\before.json') + '"', '', SW_HIDE, ewWaitUntilTerminated, Code) or (Code <> 0) then
      RaiseException('Ortak kurulum servisi başarısız. İşlem günlüğü ve yedekler ayarlar klasöründedir.');
  end;
  if CurStep = ssDone then begin
    if not Exec(ExpandConstant('{app}\respectedbrain.exe'), '_inno-seal' + RootArgs, '', SW_HIDE, ewWaitUntilTerminated, Code) or (Code <> 0) then
      RaiseException('Kaldırıcı günlüğünün son doğrulaması başarısız.');
  end;
end;

function InitializeUninstall(): Boolean;
var Code: Integer;
begin
  { Copy a verified full application to OS temp before deleting its own payload. }
  if ExpandConstant('{param:PROOF|}') = '' then begin
    Result := False;
    if not UninstallSilent then
      MsgBox('Respected Brain uygulamasını Windows uygulama listesinden kaldırın.', mbInformation, MB_OK);
    Exit;
  end;
  Result := Exec(ExpandConstant('{app}\respectedbrain.exe'), '_inno-copy-helper --app-root "' + ExpandConstant('{app}') + '" --output "' + ExpandConstant('{tmp}\helper') + '"', '', SW_HIDE, ewWaitUntilTerminated, Code) and (Code = 0);
  if Result then
    Result := Exec(ExpandConstant('{tmp}\helper\respectedbrain.exe'), '_inno-uninstall --app-root "' + ExpandConstant('{app}') + '" --data-root "' + ExpandConstant('{param:DATA|{localappdata}\RespectedBrain}') + '" --vault "' + ExpandConstant('{param:VAULT|{userdocs}\RespectedOS}') + '" --proof "' + ExpandConstant('{param:PROOF|}') + '" --proof-hash "' + ExpandConstant('{param:PROOFHASH|}') + '"', '', SW_HIDE, ewWaitUntilTerminated, Code) and (Code = 0);
end;
