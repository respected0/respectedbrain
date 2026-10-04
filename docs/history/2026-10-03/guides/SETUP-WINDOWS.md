> Tarihsel kayıt (2026-10-03). Önceki düzenin tam metnidir; güncel kurulum talimatı değildir. [Güncel rehber](../../../../README.md), [sözleşme](../../../../docs/superpowers/specs/2026-10-03-modular-foundation-design.md).

# Respected Brain — native Windows kurulumu

Bu yol Windows 10/11 üzerinde WSL, Bash veya `.sh` hook çalıştırmadan doğrudan Python kullanır.
WSL kurulumun zaten çalışıyorsa onu bozmaz; native kurulumu önce ayrı bir test vault'unda dene.

## Ön koşullar

- Git for Windows
- Gerçek Python 3 (Microsoft Store çalıştırma aliası değil)
- Seçtiğin agentlardan en az birinin giriş yapılmış CLI'ı:
  `agy`, `gemini`, `codex`, `cursor-agent` veya `claude`

## 🚀 1. Önerilen Yol: Tek Tıkla Kurulum & Bakım Paketi (`setup.exe`)

Windows kullanıcıları için en kolay, güvenli ve eksiksiz yöntem derlenmiş **`setup.exe`** paketidir.

1. **`setup.exe`** dosyasını çalıştırın.
2. Sihirbaz sisteminizi otomatik olarak tarar:
   - **İlk Kurulum:** Kullanıcı adı, Companion adı, birincil AI model önceliği (Auto, Antigravity, Codex, Claude, Gemini) ve masaüstü kısayollarını interaktif olarak yapılandırır.
   - **Mevcut Kurulum Algılandığında:** Otomatik güncelleme onayı sorar veya **Bakım Menüsü**'nü açar:
     - 🔄 **Güncelle (Update):** Notlara dokunmadan motorları günceller.
     - 🛠️ **Onar (Repair):** Eksik kancaları ve SQLite arama indeksini tamir eder.
     - ⚙️ **Değiştir (Modify):** Model ve otomasyon ayarlarını yeniden belirler.
     - 🗑️ **Kaldır (Uninstall):** Zamanlanmış görevleri ve kısayolları temizler.
3. Kurulum tamamlandığında Kontrol Paneli (`http://localhost:8520`) otomatik olarak başlar.

---

## 💻 2. Alternatif Yol: Terminalden Manuel Kurulum (Geliştiriciler İçin)

Eğer terminalden manuel kontrol ile kurmak isterseniz:

```powershell
python installer/install.py
```

veya PowerShell üzerinden ön kontrol yapmak için:

Çıktı temizse `-PreflightOnly` bölümünü kaldırıp aynı komutu yeniden çalıştır. Hedef klasör yok veya
tamamen boş olmalıdır. Kurulum sonunda `.beyin-version` `0.0.1`, `.beyin-multi-version` `0.0.1`
ve `.beyin/config.json` içindeki platform `windows-native` olur.

`-Providers` ana agentı sabitlemez; yalnız ön koşulda hangi kurulu CLI'ların doğrulanacağını söyler.
Vault her durumda Claude, Gemini, Codex, Cursor ve Antigravity adaptörlerini birlikte içerir. Sonradan agent
değiştirmek taşıma gerektirmez.

## Her kod reposundan aynı vault'a bağlanmak

Yalnız kullandığın agentların kullanıcı düzeyi bağlantılarını kur:

```powershell
py -3 runtime/scripts/install_global.py `
  "$HOME\Documents\RespectedOS" `
  --home "$HOME" `
  --platform windows-native `
  --providers codex,cursor
```

İlk çalıştırma önizlemedir. Dosyaları kontrol edip aynı komuta `--apply` ekle. Vault adının
`respectedOS` olması gerekmez.

## Sabah brifingini etkinleştirmek

Önce Task Scheduler planını salt okunur önizle:

```powershell
py -3 runtime/scripts/install_briefing_schedule.py "$HOME\Documents\RespectedOS" `
  --home "$HOME" --platform windows-native
```

Çıktı tam XML tanımını ve komutu gösterir. Onayladıktan sonra aynı komuta `--apply` ekle. Görev her
gün 08.00'de çalışır ve bilgisayar kapalıysa `StartWhenAvailable` ile açılıştan sonra aynı gün
yeniden denenir. Provider adı göreve gömülmez; değiştirilen mevcut görev tanımı
`$HOME\.respected\schedule-backups\` altında korunur.

## Mevcut Respected Brain'i güncellemek

0.0.1 öncesi veya önceki sürümlerden kalan mevcut Respected Brain vault'unu repo
kökünden güncelle:

```powershell
py -3 runtime/scripts/update_respected.py "$HOME\Documents\RespectedOS" --platform windows-native
py -3 runtime/scripts/update_respected.py "$HOME\Documents\RespectedOS" --platform windows-native --apply
```

(İsteğe bağlı `--force` bayrağı ile aynı sürümdeki dosyalar da yeniden eşitlenebilir).

İlk komut önizlemedir ve hiçbir dosya değiştirmez. Transaction staging alanı vault dışında sistem
geçici dizininde oluşturulur; yedekler `$HOME\.respected\update-backups\` altında tutulur.

Önceki sürümlerden kalan hafıza klasörleri (`🔮 850-Companion`) güvenle korunur ve taze bir Respected Brain vault'una aktarılabilir.
