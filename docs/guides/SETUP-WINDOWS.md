# Windows kurulumu

`RespectedBrain-Windows-Setup.exe` kullanıcı yetkisiyle çalışır. Program `%LOCALAPPDATA%\Programs\RespectedBrain`, ayarlar `%LOCALAPPDATA%\RespectedBrain` altındadır. Kasa ayrı seçilir. Önceki Inno dizini otomatik yeni AppRoot olmaz.

Program `respectedbrain.exe`, `app/`, `uninstall/` içerir. Sistem Python'una bağımlı değildir; kasaya `.beyin` motoru/kaldırıcı konmaz.

Kurucu `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /DIR=<program> /DATA=<ayarlar> /VAULT=<notlar>` seçeneklerini kabul eder. Native testlerde ayrı geçici klasörler kullanılır.

Çalışan program Windows update/uninstall için doğrulanmış OS-temp helper'a devreder. `pending` sonucu kuyruğa kabul anlamındadır; tamamlanmış işlem değildir. Son makbuz DataRoot/backups altına yazılır.

[Genel kurulum](SETUP.md), [güncelleme](UPDATE.md), [kaldırma](UNINSTALL.md).
