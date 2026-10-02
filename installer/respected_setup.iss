; ==============================================================================
; Respected Brain — Profesyonel Windows Kurulum & Bakım Paketi (setup.exe)
; Inno Setup 6.x Modern Akıllı Kurulum, Bakım (Modify/Repair/Update/Uninstall)
; ve Otomatik Güncelleme Yapılandırması
; ==============================================================================

#define MyAppName "Respected Brain"
#define MyAppVersion "0.0.1"
#define MyAppPublisher "Respected"
#define MyAppURL "https://github.com/respected0/respectedbrain"
#define MyAppExeName "dashboard.bat"

[Setup]
AppId={{870D0E4C-87A0-4A3C-9A82-F8E3C3A19C1D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={userdocs}\RespectedOS
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..
OutputBaseFilename=setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
WizardSizePercent=120
PrivilegesRequired=lowest
UninstallDisplayIcon={localappdata}\RespectedBrain\scripts\dashboard.bat
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription="Respected Brain — İkinci Beyin & AI Model Router Altyapısı"
VersionInfoProductName="{#MyAppName}"

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "..\template\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "*\__pycache__\*,*\__pycache__,*\.git\*,*.pyc,*.pyo"
Source: "..\runtime\*"; DestDir: "{localappdata}\RespectedBrain\runtime"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "*\__pycache__\*,*\__pycache__,*\.state\*,*\state\*,*.pyc,*.pyo,*.lock,session_start_time.*,prompt_count.*,flush-*.json,last-flush.json"
Source: "..\scripts\*"; DestDir: "{localappdata}\RespectedBrain\scripts"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "*\__pycache__\*,*\__pycache__,*.pyc,*.pyo"
Source: "install.py"; DestDir: "{localappdata}\RespectedBrain\installer"; Flags: ignoreversion
Source: "update.py"; DestDir: "{localappdata}\RespectedBrain\installer"; Flags: ignoreversion
Source: "uninstall.py"; DestDir: "{localappdata}\RespectedBrain\installer"; Flags: ignoreversion
Source: "..\setup.py"; DestDir: "{localappdata}\RespectedBrain"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName} Gateway"; Filename: "{localappdata}\RespectedBrain\scripts\dashboard.bat"
Name: "{group}\{#MyAppName} Kaldır"; Filename: "{uninstallexe}"

[UninstallRun]
Filename: "schtasks.exe"; Parameters: "/Delete /TN ""RespectedBrainBriefing"" /F"; Flags: runhidden; RunOnceId: "DelBriefing1"
Filename: "schtasks.exe"; Parameters: "/Delete /TN ""respected-morning-briefing-*"" /F"; Flags: runhidden; RunOnceId: "DelBriefing2"

[UninstallDelete]
Type: files; Name: "{userdesktop}\Respected Brain Gateway.url"
Type: files; Name: "{userdesktop}\RespectedOS.url"
Type: files; Name: "{commondesktop}\Respected Brain Gateway.url"
Type: filesandordirs; Name: "{localappdata}\RespectedBrain"

[Run]
Filename: "{localappdata}\RespectedBrain\scripts\dashboard.bat"; Description: "Respected Brain Kontrol Panelini Başlat (http://localhost:8520)"; Flags: nowait postinstall skipifsilent

[Code]
var
  MaintenancePage: TInputOptionWizardPage;
  UserPage: TInputQueryWizardPage;
  ModelPage: TInputOptionWizardPage;
  OptionsPage: TInputOptionWizardPage;
  G_ExistingInstall: Boolean;
  G_QuickUpdate: Boolean;
  G_OperationMode: Integer; // 0=NewInstall, 1=Update, 2=Repair, 3=Modify, 4=Uninstall

const
  MODE_NEW_INSTALL = 0;
  MODE_UPDATE = 1;
  MODE_REPAIR = 2;
  MODE_MODIFY = 3;
  MODE_UNINSTALL = 4;

function DetectExistingVault(): Boolean;
var
  VaultDir: String;
begin
  VaultDir := ExpandConstant('{userdocs}\RespectedOS');
  Result := DirExists(VaultDir) and (
    FileExists(VaultDir + '\.respected.json') or
    FileExists(VaultDir + '\.respectedbrain-version') or
    FileExists(VaultDir + '\.beyin-version') or
    DirExists(VaultDir + '\.beyin') or
    DirExists(VaultDir + '\scripts') or
    DirExists(VaultDir + '\🔮 850-Companion')
  );
end;

function GetPythonCommand(): String;
var
  ResCode: Integer;
begin
  if Exec(ExpandConstant('{cmd}'), '/c py.exe -3 --version', '', SW_HIDE, ewWaitUntilTerminated, ResCode) and (ResCode = 0) then
    Result := 'py.exe -3'
  else
    Result := 'python.exe';
end;

function IsPythonInstalled(): Boolean;
var
  ResCode: Integer;
begin
  Result := (Exec(ExpandConstant('{cmd}'), '/c py.exe -3 --version', '', SW_HIDE, ewWaitUntilTerminated, ResCode) and (ResCode = 0)) or
            (Exec(ExpandConstant('{cmd}'), '/c python.exe -c "import sys; sys.exit(0)"', '', SW_HIDE, ewWaitUntilTerminated, ResCode) and (ResCode = 0));
end;

function InitializeSetup(): Boolean;
var
  VaultDir: String;
  PromptMsg: String;
  BtnSelected: Integer;
  ResCode: Integer;
begin
  { Check if Python 3 is installed }
  if not IsPythonInstalled() then
  begin
    if MsgBox('Respected Brain altyapısı Python 3 ile çalışmaktadır.' + #13#10 +
              'Sisteminizde kurulu bir Python 3 tespit edilemedi.' + #13#10#13#10 +
              'Resmi indirme sayfasını açmak ister misiniz?' + #13#10 +
              '(Python yüklendikten sonra kuruluma doğrudan devam edebilirsiniz)', mbConfirmation, MB_YESNO) = IDYES then
    begin
      ShellExec('open', 'https://www.python.org/downloads/', '', '', SW_SHOWNORMAL, ewNoWait, ResCode);
    end;
    Result := False;
    Exit;
  end;

  VaultDir := ExpandConstant('{userdocs}\RespectedOS');
  G_ExistingInstall := DetectExistingVault();
  G_QuickUpdate := False;
  G_OperationMode := MODE_NEW_INSTALL;

  if G_ExistingInstall then
  begin
    PromptMsg := 'Respected Brain v0.0.1 — Mevcut Kurulum Tespit Edildi!' + #13#10#13#10 +
                 'Konum: ' + VaultDir + #13#10#13#10 +
                 'Yeni sürüme (v0.0.1) doğrudan HIZLI GÜNCELLEME yapmak istiyor musunuz?' + #13#10 +
                 '(Kişisel notlarınız, şablonlarınız ve hafızanız korunacaktır)' + #13#10#13#10 +
                 '• [Evet] : Hızlı Güncelleme (Doğrudan günceller ve paneli açar)' + #13#10 +
                 '• [Hayır] : Bakım Menüsü (Güncelle / Onar / Değiştir / Kaldır)' + #13#10 +
                 '• [İptal] : Kurulumdan Çık';

    BtnSelected := MsgBox(PromptMsg, mbConfirmation, MB_YESNOCANCEL);

    if BtnSelected = IDYES then
    begin
      if MsgBox('Respected Brain v0.0.1 güncellemesi mevcut kasaya uygulanacaktır.' + #13#10#13#10 +
                'Güncellemeyi onaylıyor musunuz?', mbConfirmation, MB_YESNO) = IDYES then
      begin
        G_OperationMode := MODE_UPDATE;
        G_QuickUpdate := True;
        Result := True;
      end
      else
      begin
        Result := False;
      end;
    end
    else if BtnSelected = IDNO then
    begin
      G_OperationMode := MODE_UPDATE;
      G_QuickUpdate := False;
      Result := True;
    end
    else
    begin
      Result := False;
    end;
  end
  else
  begin
    Result := True;
  end;
end;

procedure InitializeWizard;
var
  DefaultUser: String;
begin
  DefaultUser := ExpandConstant('{sysuserinfoname}');
  if (DefaultUser = '') or (DefaultUser = 'Username') then
    DefaultUser := 'Furkan';

  { 1. Maintenance Page (Displayed if existing installation is found) }
  MaintenancePage := CreateInputOptionPage(
    wpWelcome,
    'Respected Brain — Bakım ve Yönetim',
    'Sisteminizde mevcut bir Respected Brain kasası tespit edildi.',
    'Lütfen gerçekleştirmek istediğiniz işlemi seçin:',
    True, False
  );
  MaintenancePage.Add('🔄 Güncelle (Update) — Kasayı ve çekirdek motorları en son sürüme güncelle (Notlar korunur)');
  MaintenancePage.Add('🛠️ Onar (Repair) — SQLite arama indeksini, kancaları ve sistem şablonlarını onar');
  MaintenancePage.Add('⚙️ Değiştir (Modify) — AI model önceliğini, kullanıcı profilini ve zamanlayıcıyı yeniden yapılandır');
  MaintenancePage.Add('🗑️ Kaldır (Uninstall) — Sabah brifingi görevini, arka plan servislerini ve kısayolları kaldır');
  MaintenancePage.SelectedValueIndex := 0;

  { 2. User & Companion Information Page }
  UserPage := CreateInputQueryPage(
    wpSelectDir,
    'Kullanıcı & Companion Profili',
    'İkinci beyin düşünme ortağınızı ve kullanıcı kimliğinizi kişiselleştirin.',
    'Lütfen aşağıdaki bilgileri doğrulayın veya güncelleyin:'
  );
  UserPage.Add('1. Adınız / Hitap şekli:', False);
  UserPage.Add('2. Kısa rol veya uzmanlık alanınız:', False);
  UserPage.Add('3. Düşünme ortağınızın (Companion) adı:', False);
  UserPage.Add('4. Kasa işletim sistemi adı:', False);

  UserPage.Values[0] := DefaultUser;
  UserPage.Values[1] := 'Geliştirici & Mühendis';
  UserPage.Values[2] := 'Jarvis';
  UserPage.Values[3] := 'RespectedOS';

  { 3. AI Model & Fallback Priority Selection Page }
  ModelPage := CreateInputOptionPage(
    UserPage.ID,
    'Yapay Zeka (AI) Model ve Router Tercihi',
    'Özetleme, brifing ve analizlerde kullanılacak model ve fallback sıralamasını belirleyin.',
    'Model öncelik tercihinizi seçin:',
    True, False
  );
  ModelPage.Add('⚡ Akıllı Otomatik (Auto) — Kurulu tüm modelleri hız/maliyet sırasıyla tara (Önerilen)');
  ModelPage.Add('🪐 Google Antigravity Öncelikli (Antigravity -> Gemini -> Codex -> Claude -> Cursor)');
  ModelPage.Add('🧠 OpenAI Codex Öncelikli (Codex -> Claude -> Gemini -> Antigravity -> Cursor)');
  ModelPage.Add('🎭 Anthropic Claude Öncelikli (Claude -> Codex -> Gemini -> Antigravity -> Cursor)');
  ModelPage.Add('✨ Google Gemini Öncelikli (Gemini -> Codex -> Claude -> Antigravity -> Cursor)');
  ModelPage.SelectedValueIndex := 0;

  { 4. Integrations & Automation Tasks Page }
  OptionsPage := CreateInputOptionPage(
    ModelPage.ID,
    'Bileşenler ve Entegrasyon Seçenekleri',
    'Kasaya dahil etmek istediğiniz sistem otomasyonlarını belirleyin.',
    'Etkinleştirmek istediğiniz özellikleri işaretleyin:',
    False, False
  );
  OptionsPage.Add('Masaüstüne Respected Brain Kontrol Paneli kısayolu ekle');
  OptionsPage.Add('Her sabah 08:00''de otomatik sabah brifingi zamanla (Windows Görev Zamanlayıcı)');
  OptionsPage.Add('Global AI kural ve kanca entegrasyonu (~/.gemini, ~/.claude vb.)');
  OptionsPage.Add('Dış editörler için MCP Sunucusunu kaydet (Claude Desktop, Cursor, Antigravity)');

  OptionsPage.Values[0] := True;
  OptionsPage.Values[1] := True;
  OptionsPage.Values[2] := True;
  OptionsPage.Values[3] := True;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;

  { Fast-Track Quick Update skips all custom configuration pages }
  if G_QuickUpdate then
  begin
    if (PageID = wpSelectDir) or
       (PageID = MaintenancePage.ID) or
       (PageID = UserPage.ID) or
       (PageID = ModelPage.ID) or
       (PageID = OptionsPage.ID) then
      Result := True;
    Exit;
  end;

  { If no existing installation, skip Maintenance Page }
  if (not G_ExistingInstall) and (PageID = MaintenancePage.ID) then
  begin
    Result := True;
    Exit;
  end;

  { If existing installation: handle based on maintenance selection }
  if G_ExistingInstall then
  begin
    if PageID = wpSelectDir then
    begin
      Result := True;
      Exit;
    end;

    { If user selected Update (0) or Repair (1): skip config questions }
    if (MaintenancePage.SelectedValueIndex = 0) or (MaintenancePage.SelectedValueIndex = 1) then
    begin
      if (PageID = UserPage.ID) or (PageID = ModelPage.ID) or (PageID = OptionsPage.ID) then
        Result := True;
    end;
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  ResCode: Integer;
begin
  Result := True;

  { Handle Maintenance Page selection }
  if CurPageID = MaintenancePage.ID then
  begin
    case MaintenancePage.SelectedValueIndex of
      0: G_OperationMode := MODE_UPDATE;
      1: G_OperationMode := MODE_REPAIR;
      2: G_OperationMode := MODE_MODIFY;
      3:
      begin
        { UNINSTALL Flow }
        if MsgBox('Respected Brain zamanlanmış görevleri (RespectedBrainBriefing) ve masaüstü kısayolları kaldırılacaktır.' + #13#10 +
                  'Kişisel notlarınız ve kasa klasörünüz KESİNLİKLE SİLİNMEZ.' + #13#10#13#10 +
                  'Kaldırma işlemini onaylıyor musunuz?', mbConfirmation, MB_YESNO) = IDYES then
        begin
          { 0. Run Python uninstaller if present for comprehensive global unhook }
          if FileExists(ExpandConstant('{localappdata}\RespectedBrain\installer\uninstall.py')) then
          begin
            Exec(ExpandConstant('{cmd}'), '/c ' + GetPythonCommand() + ' "' + ExpandConstant('{localappdata}\RespectedBrain\installer\uninstall.py') + '" "' + ExpandConstant('{app}') + '" --apply --non-interactive', ExpandConstant('{localappdata}\RespectedBrain'), SW_HIDE, ewWaitUntilTerminated, ResCode);
          end
          else if FileExists(ExpandConstant('{app}\installer\uninstall.py')) then
          begin
            Exec(ExpandConstant('{cmd}'), '/c ' + GetPythonCommand() + ' "' + ExpandConstant('{app}\installer\uninstall.py') + '" "' + ExpandConstant('{app}') + '" --apply --non-interactive', ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, ResCode);
          end
          else if FileExists(ExpandConstant('{app}\uninstall.py')) then
          begin
            Exec(ExpandConstant('{cmd}'), '/c ' + GetPythonCommand() + ' "' + ExpandConstant('{app}') + '\uninstall.py" "' + ExpandConstant('{app}') + '" --apply --non-interactive', ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, ResCode);
          end;

          { 1. Delete scheduled task }
          Exec('schtasks.exe', '/Delete /TN "RespectedBrainBriefing" /F', '', SW_HIDE, ewWaitUntilTerminated, ResCode);
          Exec('schtasks.exe', '/Delete /TN "respected-morning-briefing-*" /F', '', SW_HIDE, ewWaitUntilTerminated, ResCode);

          { 2. Delete desktop shortcuts }
          DeleteFile(ExpandConstant('{userdesktop}\Respected Brain Gateway.url'));
          DeleteFile(ExpandConstant('{userdesktop}\RespectedOS.url'));
          DeleteFile(ExpandConstant('{commondesktop}\Respected Brain Gateway.url'));

          { 3. Clean runtime folder }
          DelTree(ExpandConstant('{localappdata}\RespectedBrain'), True, True, True);

          MsgBox('Respected Brain servisleri ve kısayolları sistemden başarıyla kaldırıldı.' + #13#10 +
                 'Notlarınız klasörünüzde güvenle korunmaktadır.', mbInformation, MB_OK);

          WizardForm.Close;
          Result := False;
          Exit;
        end
        else
        begin
          Result := False;
          Exit;
        end;
      end;
    end;
  end;

  { Validate User Info Page }
  if CurPageID = UserPage.ID then
  begin
    if Trim(UserPage.Values[0]) = '' then
      UserPage.Values[0] := 'Furkan';
    if Trim(UserPage.Values[2]) = '' then
      UserPage.Values[2] := 'Jarvis';
    if Trim(UserPage.Values[3]) = '' then
      UserPage.Values[3] := 'RespectedOS';
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  PyCmd: String;
  AppDir: String;
  RuntimeDir: String;
  Args: String;
  ResCode: Integer;
  DesktopUrlPath: String;
  ShortcutContent: String;
begin
  if CurStep = ssPostInstall then
  begin
    PyCmd := GetPythonCommand();
    AppDir := ExpandConstant('{app}');
    RuntimeDir := ExpandConstant('{localappdata}\RespectedBrain');

    { Ensure existing vaults are cleanly migrated to external runtime }
    Exec(ExpandConstant('{cmd}'), '/c ' + PyCmd + ' "' + RuntimeDir + '\scripts\migrate_vault_to_runtime.py" --vault "' + AppDir + '" --runtime "' + RuntimeDir + '"', RuntimeDir, SW_HIDE, ewWaitUntilTerminated, ResCode);

    { 1. UPDATE MODE }
    if (G_QuickUpdate) or (G_OperationMode = MODE_UPDATE) then
    begin
      WizardForm.StatusLabel.Caption := 'Respected Brain kasası güncelleniyor...';
      Exec(ExpandConstant('{cmd}'), '/c ' + PyCmd + ' "' + RuntimeDir + '\installer\update.py" "' + AppDir + '" --apply --platform windows-native --force', RuntimeDir, SW_HIDE, ewWaitUntilTerminated, ResCode);
      Exec(ExpandConstant('{cmd}'), '/c ' + PyCmd + ' "' + RuntimeDir + '\scripts\install_global.py" "' + AppDir + '" --platform windows-native --apply', RuntimeDir, SW_HIDE, ewWaitUntilTerminated, ResCode);
    end

    { 2. REPAIR MODE }
    else if G_OperationMode = MODE_REPAIR then
    begin
      WizardForm.StatusLabel.Caption := 'Sistem kancaları ve şablonlar onarılıyor...';
      Exec(ExpandConstant('{cmd}'), '/c ' + PyCmd + ' "' + RuntimeDir + '\scripts\update_respected.py" "' + AppDir + '" --platform windows-native --force --apply', RuntimeDir, SW_HIDE, ewWaitUntilTerminated, ResCode);
      Exec(ExpandConstant('{cmd}'), '/c ' + PyCmd + ' "' + RuntimeDir + '\scripts\install_global.py" "' + AppDir + '" --platform windows-native --apply', RuntimeDir, SW_HIDE, ewWaitUntilTerminated, ResCode);
    end

    { 3. MODIFY OR NEW INSTALL MODE }
    else
    begin
      WizardForm.StatusLabel.Caption := 'Respected Brain ve AI Router altyapısı yapılandırılıyor...';

      Args := '--non-interactive ' +
              '--user-name "' + UserPage.Values[0] + '" ' +
              '--user-bio "' + UserPage.Values[1] + '" ' +
              '--companion "' + UserPage.Values[2] + '" ' +
              '--os-name "' + UserPage.Values[3] + '" ';

      { Model and Priority mapping }
      case ModelPage.SelectedValueIndex of
        0: Args := Args + '--provider auto --priority claude codex gemini antigravity cursor ';
        1: Args := Args + '--provider auto --priority antigravity gemini codex claude cursor ';
        2: Args := Args + '--provider auto --priority codex claude gemini antigravity cursor ';
        3: Args := Args + '--provider auto --priority claude codex gemini antigravity cursor ';
        4: Args := Args + '--provider auto --priority gemini codex claude antigravity cursor ';
      end;

      { Task options }
      if OptionsPage.Values[0] then
        Args := Args + '--desktop-shortcut '
      else
        Args := Args + '--no-desktop-shortcut ';

      if OptionsPage.Values[1] then
        Args := Args + '--install-schedule --schedule-time "08:00" '
      else
        Args := Args + '--no-install-schedule ';

      if OptionsPage.Values[2] then
        Args := Args + '--install-global ';

      if OptionsPage.Values[3] then
        Args := Args + '--install-mcp '
      else
        Args := Args + '--no-install-mcp ';

      Exec(ExpandConstant('{cmd}'), '/c ' + PyCmd + ' "' + RuntimeDir + '\installer\install.py" --vault-path "' + AppDir + '" ' + Args, RuntimeDir, SW_HIDE, ewWaitUntilTerminated, ResCode);

      { Ensure vault is completely clean of any scripts/engine directories }
      Exec(ExpandConstant('{cmd}'), '/c ' + PyCmd + ' "' + RuntimeDir + '\scripts\migrate_vault_to_runtime.py" --vault "' + AppDir + '" --runtime "' + RuntimeDir + '"', RuntimeDir, SW_HIDE, ewWaitUntilTerminated, ResCode);
    end;

    { Create Desktop Gateway Shortcut if enabled or updating }
    if (G_QuickUpdate) or (OptionsPage.Values[0]) then
    begin
      DesktopUrlPath := ExpandConstant('{userdesktop}\Respected Brain Gateway.url');
      ShortcutContent := '[InternetShortcut]' + #13#10 +
                         'URL=http://localhost:8520' + #13#10 +
                         'IconIndex=0' + #13#10 +
                         'IconFile=' + RuntimeDir + '\scripts\dashboard.bat' + #13#10;
      SaveStringToFile(DesktopUrlPath, ShortcutContent, False);
    end;
  end;
end;
