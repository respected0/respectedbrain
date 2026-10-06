# 🍎🐧 macOS ve Linux Kurulumu

> Native paket kendi çalışma ortamını taşır. Kaynak geliştirme Python 3.10+ ister; bu iki yolu [genel kurulum rehberi](SETUP.md) ayırır. WSL, Linux native kurulumu ile Windows uygulamasını WSL'den çağırma bakımından farklıdır; [profil rehberine](MULTI_AI.md) bakın.

## 1. Konumlar

| Alan | macOS | Linux |
| --- | --- | --- |
| Program | `~/Applications/RespectedBrain.app` | `~/.local/lib/respectedbrain` |
| Teknik veri | `~/Library/Application Support/RespectedBrain` | `$XDG_DATA_HOME/respectedbrain`, yoksa `~/.local/share/respectedbrain` |
| Kullanıcı komutu | `.app/Contents/MacOS/respectedbrain` | `~/.local/bin/respectedbrain` |
| Not kasası | Seçtiğiniz ayrı yol | Seçtiğiniz ayrı yol |

Varsayılan kasa Documents altında `RespectedOS` olur; Documents yoksa kullanıcı kökü kullanılır. Kasa adı serbesttir. Kökler birbirini içermez. `RESPECTED_APP_DIR` özel program konumunu, `RESPECTED_DATA_DIR` ayrı teknik veri konumunu seçer. macOS özel AppRoot da `.app` sınırına uymalıdır.

## 2. Paket kabukları

macOS dağıtımındaki `setup.command`, yanında bulunan `RespectedBrain.app/Contents/MacOS/respectedbrain` launcher'ını `setup --platform posix --package ...` ile çalıştırır. Linux `setup.sh`, yanındaki `RespectedBrain/respectedbrain` launcher'ını aynı ortak hizmete bağlar. `.run` dağıtım arşivi Linux kabuğunu/payload'ı taşır. Bu kabuklar kaynak checkout'unu veya kullanıcının kasasını program payload'ı sanmaz.

Dağıtımın açılmış dizininde örnekler:

```sh
./setup.command --vault "$HOME/Documents/BenimBeynim" --no-global --no-mcp --no-schedule --no-shortcut
./setup.sh --vault "$HOME/Documents/BenimBeynim" --no-global --no-mcp --no-schedule --no-shortcut
```

İlk komut macOS, ikincisi Linux içindir; ikisi aynı pakette bulunmak zorunda değildir. Kabuklar ek argümanları ortak setup CLI'a aktarır. Kişisel profil, provider veya GUI için desteklenen seçenekler [CLI kataloğundadır](../development/CLI.md). Paket bütünlüğü ve hedef platform doğrulanır; boş yeni kasa seçilir veya kayıtlı mevcut kasa korunur.

## 3. Bağlantılar ve izinler

Global/MCP/schedule/shortcut yeni kurulumda kapalıdır. Açık `--no-*` kapatma seçimleri korunur. Etkinleştirilen kullanıcı bağlantıları ve zamanlayıcılar POSIX backend'inden yönetilir; sistem çapında kurulum veya her masaüstünde aynı kısayol davranışı varsayılmaz. Sağlayıcı CLI oturumu ve editor hook güveni ayrıca gerekir.

Gatekeeper, yayıncı imzası ve notarization, payload SHA256 doğrulamasından farklıdır. Bu projedeki hash doğrulaması tek başına macOS'un yayıncı güven zincirini sağlamaz. Burada OS güvenlik mekanizmasını devre dışı bırakma talimatı verilmez; uygulanmış sınırlar [SECURITY](../SECURITY.md) içindedir.

## 4. İlk kontrol ve bakım

Kurulum sonrası launcher ile `--version`, `vault list` ve doğru UUID'de bir test konuşmasını kontrol edin. PATH'te komut yoksa programın tam launcher yolunu kullanın. [İlk çalıştırma](BOOTSTRAP.md), [güncelleme](UPDATE.md), [yedekleme](BACKUP.md) ve [kaldırma](UNINSTALL.md) ortak sözleşmeleri kullanır.

Native macOS/Linux CI kayıtları [test matrisinde](../TEST-MATRIX.md) tarihlendirilmiştir. Bir shell dosyasının bulunması, fiziksel hostta başarıyla çalıştırıldığı veya kullanıcı hesabındaki bütün sağlayıcıların kabul edildiği kanıtı değildir.
