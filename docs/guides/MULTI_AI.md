# 🤝 Çoklu AI ve Ortak Hafıza

> Claude Code, Codex, Cursor, Antigravity ve Gemini CLI aynı kasayı kullanabilir. Hesapları veya özel chat geçmişleri birleştirilmez. Bağlanan şey notlar ve desteklenen hook/protokollerdir.

## 1. Tek instruction/skill kaynağı

Paket instructions/skills `src/respectedbrain/resources/` altında tutulur. Provider adaptörleri bunlardan üretilir. UUID'ye bağlı kişisel overrides DataRoot `vaults/<UUID>/overrides/` altındadır; migration paket defaults'undan farklı kişiselleştirmeleri burada korur. Core/Kurallar gibi insan hafıza notları kasadadır. Native Windows, WSL ve POSIX kayıtları doğru platform profiliyle kurulur.

| Sağlayıcı | Adapter/turn yolu | Gerçek kullanım şartı |
| --- | --- | --- |
| Claude Code | Claude hooks / Stop | CLI oturumu ve desteklenen hook ayarı |
| Codex | Hook/notify → ortak bridge | Notify zinciri, hook güveni ve CLI oturumu |
| Cursor | Cursor hooks / afterAgentResponse | İlgili IDE/CLI ve etkin hook |
| Antigravity | Antigravity/Gemini adaptörleri / Stop | İlgili profil ve CLI |
| Gemini CLI | Gemini hooks / AfterAgent | CLI oturumu; protokol stdout'ı temiz kalmalı |

Bu tablo mevcut kaynak adaptörlerini anlatır; tüm dış ürün sürümlerinde canlı çalıştığı garantisi değildir. Gerçek girişli ajan kabulü [test matrisinde](../TEST-MATRIX.md) fixture testinden ayrılır.

## 2. Dört optional bağlantı

`setup --global`, `--mcp`, `--schedule`, `--shortcut` açar; `--no-*` açık kapatma değeridir. Yeni defaults kapalıdır; belirtilmeyen seçenek kayıtlı değeri kullanır. `repair` kayıtlı desired-state'e göre sahipli bağlantıları onarır; kapalı seçenekleri kendiliğinden açmaz.

Global bağlantı başka kod reposunu aynı kasaya bağlar. MCP kaydı editörün stdio sunucusunu tanımlar. Schedule günlük brifing görevidir. Shortcut OS kısayoludur. Codex'te mevcut bağımsız notify zinciri korunur; tek Respected komutuyla üzerine yazılıp kaybedilmez.

## 3. Hangi AI özeti çıkarır?

```text
respectedbrain configure --summary-provider auto
respectedbrain configure --summary-provider codex
```

`summary_provider` özetleyici/model işlerinin tercihini değiştirir, ana kodlama ajanını değiştirmez. Preferences `provider_priority` ve `provider_fallback` alanları da içerir; mevcut configure CLI bu son iki alan için ayrı flag sunmaz. Elle JSON düzenlemek kilitli config update akışını baypas edebilir.

Mevcut `providers/runner.py` davranışı:

| Durum | Gerçek davranış |
| --- | --- |
| Sabit sağlayıcı + fallback false | Aday listesi yalnız seçilen sağlayıcı |
| Fallback açık | Sabit sağlayıcı varsa önce o, sonra verilmiş preferred ve priority; tekrarlar çıkarılır |
| CLI bulunamıyor | Aday atlanır; login kontrolünün başarısı sayılmaz |
| Timeout veya process çalıştırma hatası | Sonraki aday denenebilir |
| Geçici kota/ağ/5xx belirtisi | Başarısız aday sonrası fallback denenebilir |
| Genel auto (`preferred` yok/auto ve config auto) | Nonzero/stream hatasında auth/config dahil sonraki aday denenebilir; boş text de sonraki adaya geçer |
| Açık tercih ile kalıcı nonzero/stream hatası | Geçici sinyal yoksa hata döner; bütün auto çağrılarının aynı davrandığı varsayılmaz |

Dolayısıyla “kimlik doğrulama hatasında fallback daima durur” ifadesi bütün çağrılar için doğru değildir. `provider_fallback: false` auto için genel bir bütün-fallback-kapat anahtarı gibi uygulanmıyor; dar aday sınırı sabit provider dalındadır. Bu rehber davranışı belgeliyor, kodu değiştirmiyor.

Varsayılan priority paket defaults'unda Claude, Codex, Antigravity, Gemini, Cursor sırasındadır; hook'un verdiği preferred aday bunu öne alabilir. ModelRunner'ın genel çağrısı her zaman hook ajanının kimliğini parametre olarak geçirmez. Kullanım kotası gerçekten cevap veren CLI hesabına yazılır; ek API anahtarı yok diye maliyetsiz/sınırsız kullanım sözü verilmez.

## 4. Native, WSL ve POSIX

Entegrasyon profilleri `windows-native`, `windows-wsl` ve `posix` kimliklerini kullanır. Windows kurulumunun varsayılanı `windows-native` profilidir; AppRoot'taki `respectedbrain.exe` ile çalışır. Linux ve macOS kurulumu varsayılan olarak `posix` kullanır.

Windows üzerinden WSL'deki launcher'a bağlanmak için `setup --platform windows-wsl` seçilir. Bu profil `wsl.exe` köprüsü ve Windows yollarının `/mnt/...` karşılıklarını kullanır. WSL içinde ayrıca çalıştırılabilir bir `respectedbrain` launcher'ı bulunmalı ve aynı kasa UUID'si Linux DataRoot'ta çevrilmiş kasa yoluyla kayıtlı olmalıdır; profil doğrulaması bunları denetler. Global kurulumda seçili user_home/platform/CLI oturumu aynı çalıştırma ortamına ait olmalıdır; Windows ve WSL yapılandırmaları kendi ortamlarının launcher ve kimlik yollarını kullanır. `RESPECTED_RUNTIME_DIR` yeni root selector değildir; yalnız legacy okuma bağlamındadır.

## 5. MCP'nin sunduğu araçlar

| Araç | İş |
| --- | --- |
| respected_search | FTS5/BM25 tam metin arama |
| respected_get_note | Kasa içindeki notu okuma |
| respected_get_decisions | Karar/ADR notlarına erişim |
| respected_get_companion_context | İlişkisel hafıza bağlamı |
| respected_quick_capture | Inbox'a not yazma |
| respected_remember | Hafıza/kural kaydı yazma |
| respected_expand | Bilgi bağlantılarını genişletme |

İlk dördü okuma amaçlı olsa da arama indeks güncellemesi teknik veri yazabilir; son üç araçtan capture/remember not yazar. Tüm MCP araçları salt okunur değildir. Kod `respectedbrain mcp --vault-id <UUID>` stdio/JSON-RPC sunucusunu çalıştırır. Genel internet HTTP servisi değildir. [Güvenlik ve izin farkları](../SECURITY.md), [sorun giderme](TROUBLESHOOTING.md).
