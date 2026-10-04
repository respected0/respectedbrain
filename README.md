# Respected Brain

Claude Code, Codex, Cursor, Antigravity ve Gemini CLI için yerel ortak hafıza. Konuşmalar Markdown günlüklerine, kalıcı bilgiler bağlantılı notlara dönüşür. Obsidian kasanız adını ve konumunu korur.

## Üç ayrı konum

| Ne? | Windows varsayılanı | İçinde ne var? |
| --- | --- | --- |
| Program | `%LOCALAPPDATA%\Programs\RespectedBrain` | `respectedbrain.exe`, `app/` bağımlılıklar/paket kaynakları, `uninstall/` |
| Ayarlar ve teknik veri | `%LOCALAPPDATA%\RespectedBrain` | `config.json`, `install-manifest.json`, `logs/`, `backups/`, `vaults/<UUID>/state`, `cache`, `overrides` |
| Notlarınız | Örneğin `Documents\RespectedOS` | `daily/`, `knowledge/`, Companion, projeler, Templates, `.obsidian`, taşınabilir `.respected.json` kimliği |

Furkan'ın bilgisayarında ilk iki yol `C:\Users\Furkan\AppData\Local` altındadır. Belgeler konumu Windows'un yapılandırdığı klasörden alınır; başka diske yönlendirilmiş olabilir. Mevcut kasa taşınmaz.

## Kurulum

Windows native kurucusu `RespectedBrain-Windows-Setup.exe` dosyasıdır. Program klasörü ve not kasası ayrı seçilir. Native dağıtım kendi çalışma ortamını içerir; son kullanıcıya Python kurulumu gerekmez. AI özetleme için tercih ettiğiniz sağlayıcı CLI'ı kurulu ve oturum açmış olmalıdır.

[Kurulum](docs/guides/SETUP.md), [Windows](docs/guides/SETUP-WINDOWS.md), [çoklu AI](docs/guides/MULTI_AI.md), [güncelleme](docs/guides/UPDATE.md), [kaldırma](docs/guides/UNINSTALL.md).

[Kaynak kod](https://github.com/respected0/respectedbrain) üzerinde geliştirme ve native dağıtım üretimi:

```powershell
python -m pip install -e .
python -m respectedbrain --version
python tools/build_installer.py --platform windows --output dist
python tools/verify_distribution.py --distribution dist/RespectedBrain --platform windows
```

Kurulum/güncelleme doğrulanmış native paket gerektirir. Kaynaktan çalıştırmak ile bilgisayara ürün kurmak ayrı işlemlerdir.

## Önce / sonra

| Önceki düzen | Modüler düzen |
| --- | --- |
| `runtime/` ve kasada `.beyin/` motor kopyaları | Tek `src/respectedbrain/` paketi; kurulumda tek AppRoot |
| `template/`, ayrı instructions/skills kopyaları | Tek `src/respectedbrain/resources/` kaynağı |
| Motor/cache kasa içine karışabiliyordu | Teknik durum DataRoot'ta; kasa notlar için |
| Eski betiklerde ayrı kurulum davranışları | Geçiş adaptörleri ortak CLI/installation servisini çağırır |

Kişisel talimat/skill değişiklikleri migration sırasında UUID'ye bağlı `overrides/` alanına korunur. Bilinmeyen dosyalar silinmez; eski kaldırıcı çalıştırılmaz. Geçiş varsayılan olarak salt okunur önizlemedir.

## Sık sorulanlar

**Runtime nedir?** Programı çalıştıran motor ve bağımlılıklardır. AppRoot'ta yaşar. DataRoot'ta ayrı `runtime/` veya `scripts/` motoru yoktur.

**Template nedir?** Yeni boş kasaya başlangıç notları sağlar. Paket içinde kaynaktır. Mevcut notlar güncellemede şablonla değiştirilmez.

**Ayarlarım nerede?** Program tercihleri DataRoot/config.json içindedir. İnsanların okuduğu hafıza notları kasadadır. Kasa adı `RespectedOS` olmak zorunda değildir.

**Güncellersem notlarım ne olur?** Sahipli program dosyaları hash kontrolüyle güncellenir, notlar korunur. Hata halinde işlem günlüğüyle geri alınır; sonradan yapılmış kullanıcı değişiklikleri üzerine yazılmaz.

**Kaldırırsam notlarım silinir mi?** Hayır. Varsayılan kaldırma ayarları da korur. `--purge-data` yalnız doğrulanmış sahipli teknik dosyaları hedefler; not kasasını hedeflemez.

**Birden fazla kasa/ajan olabilir mi?** Kasalar UUID ile seçilir. Yazıcılar ortak kilit protokolünü kullanır. Aynı notu iki kişinin elle düzenlemesi yine dosya çakışması yaratabilir.

**Ek API anahtarı gerekir mi?** Çekirdek gerek duymaz; özetleme yerel AI CLI oturumlarını kullanır. Sağlayıcının kotası ve kullanım koşulları geçerlidir.

**Özetleyiciyi nasıl değiştiririm?** Örneğin `respectedbrain configure --summary-provider codex`. Tercih ayarlara kaydedilir; mevcut notlar ve kasa kimliği değişmez.

**Platform doğrulandı mı?** Tarihli test kanıtına bakılır. CI matrisi veya profil fixture'ı fiziksel macOS/Linux/WSL kanıtı sayılmaz.

[Yetkili mimari sözleşme](docs/superpowers/specs/2026-10-03-modular-foundation-design.md) ve [uygulama planı](docs/superpowers/plans/2026-10-03-modular-foundation.md) tasarım/devreye alma kapılarını tanımlar. Eski rehberlerin tam metni [tarihsel arşivde](docs/history/2026-10-03/README.md) korunur.

## Credits ve lisans

Bilgi derleme [Andrej Karpathy'nin LLM bilgi tabanı deseninden](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) ilham alır. Proje [Avenox Beyin](https://github.com/avenoxai/avenoxbeyin) MIT lisanslı geçmişinden doğdu; atıf ve commit geçmişi korunur. [MIT lisansı](LICENSE).
