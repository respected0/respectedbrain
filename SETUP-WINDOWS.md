# Respot Brain — native Windows kurulumu

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
pwsh -NoProfile -File scripts/install-windows.ps1 `
  -VaultPath "$HOME\Documents\AdaOS" `
  -UserName "Ada" `
  -UserBio "Kodlama ve araştırma için kullanıyor" `
  -Companion "Echo" `
  -OsName "AdaOS" `
  -Providers codex,cursor `
  -PreflightOnly
```

Çıktı temizse `-PreflightOnly` bölümünü kaldırıp aynı komutu yeniden çalıştır. Hedef klasör yok veya
tamamen boş olmalıdır. Kurulum sonunda `.beyin-version` `2.0.0`, `.beyin-multi-version` `1.1.0`
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

## Mevcut Respot Brain'i güncellemek

Damgaları `2.0.0` / `1.0.0` olan mevcut Respot vault'u repo kökünden güncelle:

```powershell
py -3 scripts/update_respot.py "$HOME\Documents\AdaOS" --platform windows-native
py -3 scripts/update_respot.py "$HOME\Documents\AdaOS" --platform windows-native --apply
```

Damgasız eski v1 vault'u native Windows üzerinde doğrudan dönüştürme henüz desteklenmez. O işlem
şimdilik WSL içindeki `scripts/upgrade.sh` ile yapılır; üretim vault'unda denemeden önce yedek al.

