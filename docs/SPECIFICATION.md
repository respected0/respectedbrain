# 📐 Respected Brain — Davranış Sözleşmesi

> Bu belge güncel kodun temel sözleşmelerine giriş sağlar. Kullanıcının onaylı tasarım kararları [modüler temel](decisions/MODULAR_FOUNDATION.md) ve [işletim ekinde](decisions/OPERATIONS.md) korunur. Son durum/kanıt burada tekrarlanmaz: [proje durumu](PROJECT_STATUS.md), [test matrisi](TEST-MATRIX.md).

## 1. Paket ve kimlik

| Konu | Sözleşme / kaynak |
| --- | --- |
| Sürüm | `pyproject.toml` paket metadata'sı; `respectedbrain.__version__` / `--version` buradan sunar |
| Kaynak desteği | Python 3.10+; native dağıtım kendi çalışma ortamını içerir |
| Config | DataRoot/config.json, `schema_version: 3`; bozuk/eski şema sessizce defaults'a dönmez |
| Kasa marker | VaultRoot/.respected.json, schema 3 ve kalıcı UUID; makine yolları config'te |
| Ayrı kökler | AppRoot, DataRoot ve VaultRoot birbirini içermez |
| Ajanlar | Claude Code, Codex, Cursor, Antigravity, Gemini CLI; hiçbiri tek zorunlu sağlayıcı değildir |

`vault register` marker/registry yazabilir; salt okunur listeleme komutu değildir. Kasa kaydı motor kurulumu veya hazır yeni template kurulumu yerine geçmez. Kopyalanmış aynı UUID'li kasa çakışır; `--new-identity` açıkça yeni kimlik verir.

## 2. Seçim ve yapılandırma

Kasa seçim sırası açık `--vault` veya `--vault-id`, `RESPECTED_VAULT_PATH`, config `active_vault_id` şeklindedir. İki selector birlikte kabul edilmez. Açık geçersiz seçim başka kasaya fallback yapmaz. `RESPECTED_APP_DIR` ve `RESPECTED_DATA_DIR` mutlak kök override'larıdır; macOS AppRoot `.app` sınırına uyar. Native Windows ile WSL profil/çalıştırıcı farkı [çoklu AI rehberinde](guides/MULTI_AI.md).

Config dosyası yoksa paket defaults okunur; update kilit altında tekrar okuyarak atomik yazar. Bilinmeyen kullanıcı alanları korunur. `summary_provider`, `provider_priority`, `provider_fallback` preferences'tadır; dört isteğe bağlı bağlantı `integrations` içindedir. Varsayılan global/MCP/schedule/shortcut kapalıdır; belirtilmeyen seçenek mevcut tercihleri kullanır, açık false kapalı kalır.

## 3. Kurulum ve yaşam döngüsü

| İşlem | Korunan sınır |
| --- | --- |
| setup | Doğrulanmış native paket, boş yeni hedef veya geçerli kayıtlı kasa; bilinmeyen dolu hedefe template yazılmaz |
| update | Doğrulanmış yeni paket, aynı kimlik/tercihler, notlar template ile yenilenmez |
| repair | Sahipli program/bağlantı alanları; insan notlarını yeniden başlatmaz |
| uninstall | Yalnız kanıtlı sahiplik ve değişmemiş hash; kasa ve `.obsidian` hedef değildir |
| purge-data / keep-data | Varsayılan (ve açık --purge-data) yalnız kanıtlı sahipli teknik dosyaları temizler; --keep-data teknik veriyi korur; not kasası hiçbir zaman silinmez |
| migrate | Varsayılan salt okunur plan; conflict varsa apply yapılmaz; değişiklik açık `--apply` ister |
| recover | Yarım transaction'lar hash karşılaştırmasıyla geri alınır; eşzamanlı kullanıcı değişikliği korunur |

Transaction journal/byte yedeği, kilit, compare-and-swap ve faz kontrolleri kullanılır. Eski geniş silme yapan uninstaller çalıştırılmaz. Pending Windows sonucu son receipt doğrulanmadan tamamlandı sayılmaz; exit 0 işlem kuyruğa alındığında da gelebilir.

## 4. Protokol ve hafıza

Hook/MCP stdout protokol çıktısıdır; tanı stderr veya teknik log alanındadır. Özet çıktı biçimi doğrulanır, daily yönetilen session bloğu kilit altında upsert edilir. Format doğrulaması içeriğin gerçeği yansıttığını kanıtlamaz. Kapanış/catch-up, desteklenmeyen veya devre dışı her hook olayının eksiksiz yakalandığı garantisi değildir.

Derleme terfisi allowlist knowledge yolları, path/symlink/reparse, kaynak/hedef hash ve eşzamanlı değişiklik kontrollerine bağlıdır. Sağlayıcı süreç izinleri eşdeğer değildir. FTS5 araması, harici web alımı, Git snapshot ve yerel panel ayrı güvenlik sınırları taşır; [SECURITY](SECURITY.md) uygulanmış kontrol ile kalan açığı ayırır.

## 5. Doğrulama dürüstlüğü

Kaynak unit test, gerçek frozen binary, native OS kabul, WSL köprüsü ve giriş yapılmış sağlayıcı kabulü ayrı kanıtlardır. Birindeki başarı diğerinin otomatik kanıtı değildir. CI yeşil olması snapshot secret taraması, OS sandbox veya yayıncı imzasını eklemez. Çalıştırılmamış platform başarılı diye yazılmaz.

Komutların tüm seçenekleri [CLI kataloğunda](development/CLI.md), dosya sorumlulukları [atlasta](REPOSITORY_MAP.md) bulunur. Kod değişince bu belge aynı görevde incelenir.
