# ⌨️ CLI Komut ve Seçenek Kataloğu

> Tablolar mevcut `cli._parser()` tanımlarından, komut çalıştırmadan üretildi. Kullanıcı rehberleri [belge merkezinde](../README.md). `<...>` örnekleri gerçek değerle değiştirilir. `respectedbrain` PATH yoksa tam native yol; kaynakta `python -m respectedbrain` kullanılır.

## 1. Çıkış kodları ve yan etkiler

Genel seçim/argüman hatası 2; Foundation/OS hatası 1; normal başarı 0. Setup/update/uninstall pending sonucu da 0 dönebilir: son receipt ayrıca doğrulanır. Search/maps/maintenance salt okunur kabul edilmez. Hook/MCP stdout protokoldür. `--help` ve `--version` kullanıcı kurulumu yapmaz.

## 2. Genel seçenekler

`respectedbrain --version`, `respectedbrain --help`; komut help örneği `respectedbrain setup --help`. Kasa selector destekleyen komutlarda --vault ile --vault-id birbirini dışlar. Configure/vault/recover/setup/migrate farklı seçim arayüzlerine sahiptir; her komuta aynı flag uygulanmaz.

### vault

Kasa kaydı/keşfi/listesi. register yazabilir; list/discover kurulum yapmaz.

#### vault register

| Argüman | Gereklilik / varsayılan | Değerler |
| --- | --- | --- |
| `path` | zorunlu | Path |
| `--new-identity` | isteğe bağlı; default: False | flag |

#### vault list

Ek argüman yoktur.

#### vault discover

| Argüman | Gereklilik / varsayılan | Değerler |
| --- | --- | --- |
| `path` | zorunlu | Path |

### configure

Ayar gösterir; --summary-provider varsa atomik config yazar.

| Argüman | Gereklilik / varsayılan | Değerler |
| --- | --- | --- |
| `--summary-provider` | isteğe bağlı | auto, codex, claude, antigravity, gemini, cursor |

### briefing

Zamanı gelmiş günlük derleme/brifing; model/not yazımı olabilir.

| Argüman | Gereklilik / varsayılan | Değerler |
| --- | --- | --- |
| `--vault` | isteğe bağlı | Path |
| `--vault-id` | isteğe bağlı | metin/argv |

### maps

Seçili kasanın haritalarını üretir; not yazar.

| Argüman | Gereklilik / varsayılan | Değerler |
| --- | --- | --- |
| `--vault` | isteğe bağlı | Path |
| `--vault-id` | isteğe bağlı | metin/argv |

### compile

Model ile knowledge derler; --dry-run önizleme.

| Argüman | Gereklilik / varsayılan | Değerler |
| --- | --- | --- |
| `--vault` | isteğe bağlı | Path |
| `--vault-id` | isteğe bağlı | metin/argv |
| `--trigger-claim` | isteğe bağlı | Path |
| `--before-date` | isteğe bağlı | YYYY-MM-DD |
| `--max-calls` | isteğe bağlı | int |
| `--dry-run` | isteğe bağlı; default: False | flag |

### flush

Transcript + session özetleyip daily yazar; gelişmiş hook işleri.

| Argüman | Gereklilik / varsayılan | Değerler |
| --- | --- | --- |
| `--vault` | isteğe bağlı | Path |
| `--vault-id` | isteğe bağlı | metin/argv |
| `--hook-input` | isteğe bağlı | Path |
| `--transcript` | isteğe bağlı | Path |
| `--session-id` | isteğe bağlı | metin/argv |
| `--reason` | isteğe bağlı; default: sessionend | metin/argv |
| `--maybe-compile` | isteğe bağlı; default: False | flag |

### dashboard

Loopback HTTP paneli; process sunucu açıkken devam eder.

| Argüman | Gereklilik / varsayılan | Değerler |
| --- | --- | --- |
| `--vault` | isteğe bağlı | Path |
| `--vault-id` | isteğe bağlı | metin/argv |
| `--port` | isteğe bağlı; default: 8520 | int |
| `--open` | isteğe bağlı; default: False | flag |

### search

FTS araması; teknik indeks/cache yazabilir.

| Argüman | Gereklilik / varsayılan | Değerler |
| --- | --- | --- |
| `--vault` | isteğe bağlı | Path |
| `--vault-id` | isteğe bağlı | metin/argv |
| `query` | isteğe bağlı; default: boş metin | metin/argv |
| `--reindex` | isteğe bağlı; default: False | flag |
| `--category` | isteğe bağlı | metin/argv |
| `--limit` | isteğe bağlı; default: 10 | int |
| `--json` | isteğe bağlı; default: False | flag |

### orchestrate

Açık kod projesinde worker; komut/provider süreçleri çalıştırır.

| Argüman | Gereklilik / varsayılan | Değerler |
| --- | --- | --- |
| `--vault` | isteğe bağlı | Path |
| `--vault-id` | isteğe bağlı | metin/argv |
| `--project-root` | zorunlu | Path |
| `argv` | isteğe bağlı | metin/argv |

### maintenance

İsimli bakım aracı; yan etkisi seçilen araca bağlı.

| Argüman | Gereklilik / varsayılan | Değerler |
| --- | --- | --- |
| `--vault` | isteğe bağlı | Path |
| `--vault-id` | isteğe bağlı | metin/argv |
| `name` | zorunlu | metin/argv |
| `argv` | isteğe bağlı | metin/argv |

### setup

Doğrulanmış native paketi kurar, boş kasa seed ve bağlantıları yönetir.

| Argüman | Gereklilik / varsayılan | Değerler |
| --- | --- | --- |
| `--vault` | isteğe bağlı | Path |
| `--package` | isteğe bağlı | Path |
| `--gui` | isteğe bağlı; default: False | flag |
| `--user-name` | isteğe bağlı | metin/argv |
| `--user-bio` | isteğe bağlı | metin/argv |
| `--companion` | isteğe bağlı | metin/argv |
| `--os-name` | isteğe bağlı | metin/argv |
| `--summary-provider` | isteğe bağlı | auto, codex, claude, antigravity, gemini, cursor |
| `--platform` | isteğe bağlı | windows-native, posix, windows-wsl |
| `--global, --no-global` | isteğe bağlı | flag |
| `--mcp, --no-mcp` | isteğe bağlı | flag |
| `--schedule, --no-schedule` | isteğe bağlı | flag |
| `--shortcut, --no-shortcut` | isteğe bağlı | flag |

### update

Yeni doğrulanmış paketten günceller; Windows pending olabilir.

| Argüman | Gereklilik / varsayılan | Değerler |
| --- | --- | --- |
| `--vault` | isteğe bağlı | Path |
| `--vault-id` | isteğe bağlı | metin/argv |
| `--package` | zorunlu | Path |

### repair

Sahipli program/desired bağlantıları onarır.

| Argüman | Gereklilik / varsayılan | Değerler |
| --- | --- | --- |
| `--vault` | isteğe bağlı | Path |
| `--vault-id` | isteğe bağlı | metin/argv |

### uninstall

Sahipli program/bağlantıları kaldırır; not kasasını hedeflemez.

| Argüman | Gereklilik / varsayılan | Değerler |
| --- | --- | --- |
| `--vault` | isteğe bağlı | Path |
| `--vault-id` | isteğe bağlı | metin/argv |
| `--purge-data` | isteğe bağlı; default: False | flag |

### migrate

Legacy varsayılan salt okunur plan; --apply mutasyon.

| Argüman | Gereklilik / varsayılan | Değerler |
| --- | --- | --- |
| `--legacy-root` | zorunlu | Path |
| `--vault` | zorunlu | Path |
| `--package` | isteğe bağlı | Path |
| `--apply` | isteğe bağlı; default: False | flag |
| `--platform` | isteğe bağlı | windows-native, posix, windows-wsl |

### recover

Yarım transaction recovery; conflict varsa exit 1. Ek argüman yoktur.

### hook

Provider olay protokolü. Üretilmiş hook kayıtları içindir.

| Argüman | Gereklilik / varsayılan | Değerler |
| --- | --- | --- |
| `--vault` | isteğe bağlı | Path |
| `--vault-id` | isteğe bağlı | metin/argv |
| `--provider` | zorunlu | claude, codex, cursor, antigravity, gemini |
| `--event` | zorunlu | start, prompt, precompact, postcompact, turn, end, notify |
| `--global-hook` | isteğe bağlı; default: False | flag |
| `--chain-file` | isteğe bağlı | Path |
| `payload` | isteğe bağlı | metin/argv |

### mcp

Stdio JSON-RPC sunucusu; çağrılan araçlar okuma/yazma yapabilir.

| Argüman | Gereklilik / varsayılan | Değerler |
| --- | --- | --- |
| `--vault` | isteğe bağlı | Path |
| `--vault-id` | isteğe bağlı | metin/argv |

## 3. Bakım araçları

İsimler `maintenance._TOOLS` kaynağıyla karşılaştırılmıştır. Kasa selector tool isminden önce yazılır; araç seçenekleri sonradan aktarılır. Bilinmeyen araç açık hata verir.

| İsim | İş / yan etki |
| --- | --- |
| repair_daily | Daily kayıt düzeltmesi; not yazabilir |
| vault_linter | Not metadata/yapı denetimi |
| architect_scan | Vault mimari/yapı analizi |
| smart_merge | Not birleştirme; hedef dosya değişebilir |
| tiling_check | Not/yerleşim denetimi |
| backup_restic | Harici Restic; --repo zorunlu, --apply gerçek yedek, --skip-verify restore kontrolünü kapatır |
| publish_git_snapshot | --remote/--branch; --apply gerçek Git yayını; preview fetch yapabilir |
| mine_agent_history | Yerel ajan geçmişini işleme; not yazabilir |
| defuddle | URL ingestion; ağ ve not yazımı; SSRF transport sınırı var |

Her araç kendi parser help çıktısını sunar; kapsamı uygulamadan önce `respectedbrain maintenance --vault-id <UUID> <araç> --help` ile kontrol edin. Tool argümanına başka kasa vererek seçili context dışına çıkılamaz.

## 4. İç OS protokol komutları

Alt çizgiyle başlayan `_resume-operation` ve `_inno-*` komutları hash doğrulanmış shell/helper protokolüdür. Kullanıcı bakım komutu gibi elle çağrılmaz; request/proof doğrulama sözleşmesini atlamak için kullanılamaz. Kesin arayüz `cli.py`, `installation/windows.py`, `deferred.py` içindedir.
