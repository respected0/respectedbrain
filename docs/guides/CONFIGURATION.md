# ⚙️ Ayarlar ve Kasa Seçimi

> Makine ayarları DataRoot'ta; insan hafızası ve taşınabilir kasa kimliği VaultRoot'tadır. [Konum tablosu](../ARCHITECTURE.md).

## 1. Hangi dosya neyi tutar?

| Dosya / dizin | İçerik |
| --- | --- |
| DataRoot/config.json | Schema 3, active_vault_id, UUID→yol registry, kasa settings, preferences ve integrations |
| DataRoot/install-manifest.json | Sahipli dosya hash/mode ve external kayıt kanıtı; elle yeniden üretmeyin |
| DataRoot/vaults/<UUID>/state | Tekrar kontrolü, oturum/worker teknik durumu |
| DataRoot/vaults/<UUID>/cache | FTS/derleme gibi yeniden üretilebilir teknik cache |
| DataRoot/vaults/<UUID>/overrides | Kişisel instruction/skill override alanı |
| VaultRoot/.respected.json | Schema 3 ve kalıcı UUID; makine yolu burada değildir |
| VaultRoot/🔮 850-Companion | İnsan tarafından okunup düzenlenen kimlik, kurallar, konular ve devir |

Paket `resources/defaults.json` yeni config'in varsayılan kaynağıdır; mevcut kullanıcı config'inin üzerine kopyalanmaz. Config bilinmeyen alanları korur. Bozuk JSON/eski şema hata verir; sessiz sıfırlama yapılmaz.

## 2. Güvenli komutlar ve yazan komutlar

```text
respectedbrain configure
respectedbrain vault list
respectedbrain configure --summary-provider codex
respectedbrain vault register "<mevcut kasa yolu>"
```

İlk ikisi ayar/kayıt gösterir. Provider değiştirme config yazar. Register marker ve config yazabilir, gerekirse marker'ın önceki halini yedekler; setup/template kurmuş sayılmaz. `vault register --new-identity` aynı UUID'li kopyayı ayrı kasa yapabilir; mevcut kasaya rutin olarak uygulanmaz. `vault discover <path>` marker arar, bulunması otomatik motor kurulumu değildir.

## 3. Kasa seçimi

1. Açık `--vault "<yol>"` veya `--vault-id <UUID>`.
2. `RESPECTED_VAULT_PATH`.
3. Config `active_vault_id`.

İki selector birden hata verir. Kasa path'i registry ve marker UUID ile uyuşmalıdır; başka klasöre aynı UUID kopyalanırsa conflict olur. Yanlış açık yol için sessiz başka kasaya geçilmez. Active-vault değiştirmek için mevcut CLI'da ayrı `vault activate` komutu yoktur; işlem sırasında açık UUID seçmek en anlaşılır yoldur.

## 4. Kök ve model environment değişkenleri

| Değişken | Kapsam |
| --- | --- |
| RESPECTED_APP_DIR | Mutlak uygulama kökü; kasa/data'dan ayrı |
| RESPECTED_DATA_DIR | Mutlak teknik veri kökü; başka kayıt alanına geçer |
| RESPECTED_VAULT_PATH | Kayıtlı kasanın açık yol seçimi |
| XDG_DATA_HOME | Linux varsayılan teknik veri tabanı |
| RESPECTED_RUNTIME_DIR | Eski layout okumada legacy ipucu; yeni motor kökü değildir |
| BEYIN_LLM_COMMAND | Eski özel komut anahtarı. Tanımlandığında `custom-isolation-required` ile child başlatılmadan reddedilir |

Environment override'ları farklı DataRoot/registry seçebilir; “notlar kayboldu” sanmadan kullanılan kökü kontrol edin. Özel model komutu doğrulanmış bir OS sandbox sınırı sunmadığı için çalıştırılmaz; bu değişken yalnız uyumsuz çağrıyı güvenli biçimde reddetmek için okunur.

## 5. Tercihler

Summary provider `auto/codex/claude/antigravity/gemini/cursor`; defaults priority ve fallback [çoklu AI rehberinde](MULTI_AI.md). Global/MCP/schedule/shortcut defaults false. Kasa settings kullanıcı/companion adı ve OS/user_home profili taşır. Aynı alanların paket defaults'unda bulunması kullanıcı config'ini otomatik yenilemez.

Config'i uygulama çalışırken elle değiştirmek atomik/lock korumasını baypas eder. Mevcut CLI sadece `--summary-provider` için doğrudan preference flag'i sunar; belgelenmemiş flag icat etmeyin. [CLI kataloğu](../development/CLI.md).
