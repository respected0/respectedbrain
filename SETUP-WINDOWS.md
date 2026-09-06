# Respected Brain — native Windows kurulumu

Bu yol Windows 10/11 üzerinde WSL, Bash veya `.sh` hook çalıştırmadan doğrudan Python kullanır.
WSL kurulumun zaten çalışıyorsa onu bozmaz; native kurulumu önce ayrı bir test vault'unda dene.

## Ön koşullar

- Git for Windows
- Gerçek Python 3 (Microsoft Store çalıştırma aliası değil)
- Seçtiğin agentlardan en az birinin giriş yapılmış CLI'ı:
  `agy`, `codex`, `cursor-agent` veya `claude`

Kurucu paket yöneticisi çalıştırmaz ve hesap girişi yapmaz. Eksik araç varsa önerilen komutu yazıp
durur. PowerShell'de önce yalnız ön kontrol yap:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/install-windows.ps1 `
  -VaultPath "$HOME\Documents\AdaOS" `
  -UserName "Ada" `
  -UserBio "Kodlama ve araştırma için kullanıyor" `
  -Companion "Echo" `
  -OsName "AdaOS" `
  -Providers codex,cursor `
  -PreflightOnly
```

Çıktı temizse `-PreflightOnly` bölümünü kaldırıp aynı komutu yeniden çalıştır. Hedef klasör yok veya
tamamen boş olmalıdır. Kurulum sonunda `.beyin-version` `2.0.0`, `.beyin-multi-version` `1.4.0`
ve `.beyin/config.json` içindeki platform `windows-native` olur.

`-Providers` ana agentı sabitlemez; yalnız ön koşulda hangi kurulu CLI'ların doğrulanacağını söyler.
Vault her durumda Claude, Codex, Cursor ve Antigravity adaptörlerini birlikte içerir. Sonradan agent
değiştirmek taşıma gerektirmez.

## Her kod reposundan aynı vault'a bağlanmak

Yalnız kullandığın agentların kullanıcı düzeyi bağlantılarını kur:

```powershell
py -3 scripts/install_global.py `
  "$HOME\Documents\AdaOS" `
  --home "$HOME" `
  --platform windows-native `
  --providers codex,cursor
```

İlk çalıştırma önizlemedir. Dosyaları kontrol edip aynı komuta `--apply` ekle. Vault adının
`respectedOS` olması gerekmez.

## Sabah brifingini etkinleştirmek

Önce Task Scheduler planını salt okunur önizle:

```powershell
py -3 scripts/install_briefing_schedule.py "$HOME\Documents\AdaOS" `
  --home "$HOME" --platform windows-native
```

Çıktı tam XML tanımını ve komutu gösterir. Onayladıktan sonra aynı komuta `--apply` ekle. Görev her
gün 08.00'de çalışır ve bilgisayar kapalıysa `StartWhenAvailable` ile açılıştan sonra aynı gün
yeniden denenir. Provider adı göreve gömülmez; değiştirilen mevcut görev tanımı
`$HOME\.respected\schedule-backups\` altında korunur.

## Mevcut Respected Brain'i güncellemek

Damgaları `2.0.0` / `1.0.0`, `1.1.0` veya `1.2.0` olan mevcut Respected Brain vault'unu repo
kökünden güncelle:

```powershell
py -3 scripts/update_respected.py "$HOME\Documents\AdaOS" --platform windows-native
py -3 scripts/update_respected.py "$HOME\Documents\AdaOS" --platform windows-native --apply
```

İlk komut önizlemedir ve hiçbir dosya değiştirmez. Transaction staging alanı vault dışında sistem
geçici dizininde oluşturulur; yedekler `$HOME\.respected\update-backups\` altında tutulur.

Damgasız eski v1 vault'u native Windows üzerinde doğrudan dönüştürme henüz desteklenmez. O işlem
şimdilik WSL içindeki `scripts/upgrade.sh` ile yapılır; üretim vault'unda denemeden önce yedek al.
