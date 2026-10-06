# 🚀 Kurulum Rehberi

> Program dosyalarını, teknik veriyi ve not kasasını ayrı kurun. [Mimari](../ARCHITECTURE.md) konumları, [Windows rehberi](SETUP-WINDOWS.md) kurucu ayrıntısını açıklar.

## 1. Hangi kurulumu seçmeliyim?

| Yol | Gereken | Sonuç |
| --- | --- | --- |
| Native dağıtım | Hedef OS için doğrulanmış paket | Program kendi çalışma ortamını içerir; kullanıcıya Python gerekmez |
| Kaynak geliştirme | Python 3.10+, editable paket ve dev araçları | Kod/CLI geliştirme; bilgisayara native motor kurmuş sayılmaz |

Kaynak repo clone etmek, wheel kurmak veya kasa kaydetmek, AppRoot'a native dağıtım yerleştirmekle aynı değildir. Setup/update hizmetleri `distribution.json` taşıyan doğrulanmış native payload bekler. Paket üretimi [geliştirici rehberinde](../development/README.md).

## 2. Kurulumdan önce

1. Programı koyacağınız AppRoot, teknik veri DataRoot ve not kasası VaultRoot ayrı yollar olmalı; birbirini içermemeli.
2. Yeni kasa için boş hedef seçin. Mevcut dolu kasaya fresh template uygulanmaz; kayıtlı modern kasa veya [migration/kayıt sözleşmesi](UPDATE.md) ile korunur. Bilinmeyen dolu hedefe kurulum zorlamayın.
3. AI işler için kullanacağınız sağlayıcı CLI'ını kurup oturum açın. Programın dosya/arama işlemleri için her sağlayıcıya giriş yapmak gerekmez.
4. Eski kişisel kasanız varsa [yedekleme](BACKUP.md) rehberini uygulayın. Yeni boş kasa açmak eski notları aktarmayı zorunlu kılmaz.

## 3. Native kurulum

Windows: kurucuda program ve kasa ayrı seçilir. macOS: platform dağıtımındaki `setup.command`; Linux: platform dağıtımındaki `setup.sh`/`.run` kabuğu ortak setup komutuna bağlanır. Paket kabuğu ve OS konum ayrıntıları [macOS/Linux rehberinde](SETUP-POSIX.md) açıklanır; doğrulama ilgili platform üzerinde yapılır.

Kurulu/dağıtım launcher'ıyla CLI örneği:

```text
respectedbrain setup --vault "<not kasası>" --package "<doğrulanmış dağıtım>"
respectedbrain setup --gui --vault "<not kasası>" --package "<doğrulanmış dağıtım>"
```

`<...>` alanları gerçek mutlak yollarla değiştirilir. Windows'ta CLI adı `respectedbrain.exe`; PATH'e eklenmemişse tam executable yolunu kullanın. macOS'ta launcher `.app/Contents/MacOS/respectedbrain` içindedir. Doğrulanmamış veya başka OS için üretilmiş paketi kaynak package klasörü sanmayın.

## 4. Dört isteğe bağlı bağlantı

| Seçenek | Ne açar? | CLI |
| --- | --- | --- |
| global | Başka kod projelerinde kullanıcı düzeyi beyin bağlantısı | `--global` / `--no-global` |
| mcp | Editör MCP kayıtları | `--mcp` / `--no-mcp` |
| schedule | Sabah brifingi zamanlayıcısı | `--schedule` / `--no-schedule` |
| shortcut | OS kısayolu | `--shortcut` / `--no-shortcut` |

Yeni kurulumda bunlar **kapalıdır**. Yeniden kurulum kapalı tercihleri açmaz; verilmemiş seçenekler kayıtlı defaults'tan alınır, açık false korunur. Global bağlantı/mcp kaydı gerçek kullanıcı profiline yazabilir; seçili OS/WSL profiliyle kurulmalıdır. Ayrıntı [çoklu AI](MULTI_AI.md).

## 5. Kökler ve ilk kontrol

`RESPECTED_APP_DIR` ve `RESPECTED_DATA_DIR` mutlak kök override'larıdır. Linux AppRoot `~/.local/lib/respectedbrain`, DataRoot `$XDG_DATA_HOME/respectedbrain` veya `~/.local/share/respectedbrain`. macOS AppRoot `~/Applications/RespectedBrain.app`, DataRoot `~/Library/Application Support/RespectedBrain`; özel AppRoot da `.app` olmalı, runtime `Contents/Frameworks` içinde bulunur.

```text
respectedbrain --version
respectedbrain vault list
respectedbrain maps --vault-id <UUID>
respectedbrain search --vault-id <UUID> --json "aranan kelime"
```

Maps ve search yazabilen işlemlerdir: harita/teknik indeks üretir. Kurulum sonrası kişiselleştirme ve gerçek konuşma kabulü [ilk çalıştırma rehberinde](BOOTSTRAP.md). Bir exit code veya fixture başarısı giriş yapılmış ajan hook'unun çalıştığını tek başına kanıtlamaz.
