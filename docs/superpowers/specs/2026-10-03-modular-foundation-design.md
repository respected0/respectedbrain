---
title: Respected Brain — Modüler Temel ve Kurulum Sözleşmesi
created: 2026-10-03
scope: project
confidence: inferred
supersedes: []
status: written-spec-approved
timeline:
  - from: 2026-10-03
    until: 2026-10-03
    learned: Yazılı sözleşme kullanıcı incelemesini bekliyordu; kullanıcı onayladı.
    source: "the human partner reviews and approves the written spec"
---

# Respected Brain — Modüler Temel ve Kurulum Sözleşmesi

Kullanıcı 2026-10-03 tarihinde önce/sonra açıklamasındaki mimari yönü kabul etti:
“bu sistemi beğendim. bu mimariye kesinlikle geçmeliyiz”. Bu belge o yönün
uygulanabilir sözleşmesidir. Kullanıcı yazılı sözleşmeyi de 2026-10-03 tarihinde
onayladı; uygulama planı ayrı inceleme aşamasındadır. Hedef yerleşim mevcut
kurulumun bugün bu şekilde çalıştığı anlamına gelmez.

## Kısa okuma: ne değişecek?

1. Kaynak kodlar `src/respectedbrain` altında işlerine göre ayrılacak.
2. Kurulu program `Local/Programs/RespectedBrain` altında tek kopya olacak.
3. Ayarlar ve teknik kayıtlar `Local/RespectedBrain` altında korunacak.
4. Notların mevcut RespectedOS kasasında kalacak; motor/cache oradan ayrılacak.
5. Bütün kurucular aynı işlemleri kullanacak; eski veri önce yedeklenecek.

Program güncellemesi programı değiştirecek; kullanıcının notlarını şablonla
yeniden oluşturmayacak. Bu belgede **yerleşim/modül eşleştirme tablosunu**,
alt belgede **geçiş ve veri koruma kurallarını** incelemek tasarımın özünü verir.

## 1. Amaç ve kapsam

İlk iş mevcut özellikleri yeni bir zemine taşımaktır: tek uygulama paketi,
ortak giriş noktası, görevine göre ayrılmış modüller ve birbirinden bağımsız
program/veri/kasa konumları. Yeni brifing, arama, panel veya ajan özelliği
eklenmez. AI sağlayıcılarının mevcut CLI davranışı korunur.

Başarı, klasörlerin yalnızca yeniden adlandırılması değildir. Bütün girişler
aynı kodu çalıştırmalı; kurulum aynı son yerleşimi üretmeli; program güncellemesi
kullanıcı notlarını ve ayarlarını değiştirmemelidir.

Birincil dağıtım Windows'ta tek kullanıcı içindir, yönetici izni istemez.
Önceki açıklamada kabul edilen varsayılan budur. macOS/Linux aynı paket ve
modül sözleşmesini kullanır; işletim sistemine özgü yollar uyarlanır.
Makine geneli kurulum, taşınabilir mod, mikroservisler ve ayrı plugin yükleme
sistemi bu geçişin kapsamına dahil değildir.

Önceki yol düzeltmeleri çalışma ağacındadır. Taşıma onların üzerine yapılır;
geri alınmaz veya eski commit'ten sessizce yeniden üretilmez. Önceki görevdeki
“dosya taşıma” sınırı o yol onarımı için geçerliydi; kullanıcı şimdi mimari
geçiş yönünü açıkça seçmiştir. Bu belgeyi hazırlamak kod taşıma ya da canlı
kurulum dönüşümü yapmaz.

## 2. Mevcut durum: doğrulanmış gözlemler

2026-10-03 envanteri:

- Kaynak repo: `runtime/`, `template/`, `installer/`, `tests/`, `docs/` ve
  farklı platformların setup başlatıcıları.
- `runtime/scripts/` arama, MCP, bakım, kurulum, panel ve paket üretimini
  birlikte içeriyor. Importlar dosya yerleşimine ve `sys.path` eklemelerine bağlı.
- Windows Inno paketi runtime'ı iç içe dizine, scripts'i ayrıca köke açıyor.
  Geçiş betiği runtime içeriğini bir de uygulama köküne kopyalıyor.
- Kurulu `%LOCALAPPDATA%/RespectedBrain` içinde kökte `engine`, `gateway`,
  `scripts` ve ayrıca `runtime/engine`, `runtime/gateway`, `runtime/scripts` var.
- Canlı not kasasında `.beyin/cache`, `.beyin/engine` ve Inno kaldırıcı
  `unins000.exe/dat` artıkları bulunuyor.
- Doğrudan Python/PowerShell kurulumu ile Inno'nun son geçiş akışı aynı değil.
- Mevcut migration geniş klasör temizliği yapıyor ve global bağlantıyı
  seçenekten bağımsız yeniden kurabiliyor.

Önceki oturumda 24 yol regresyon testi dahil 447 Python testi başarılıydı;
10 test atlandı. Native PowerShell, Task Scheduler ve platform smoke
kontrolleri geçti. Bu tarihli kanıt yeni mimarinin doğrulandığı iddiası değildir.
Grafik Inno kurulumunun gerçek makinede uçtan uca testi yapılmamıştır.

## 3. Üç konum ve sahiplik

### 3.1 Program: AppRoot

Windows varsayılanı: `%LOCALAPPDATA%/Programs/RespectedBrain`.

```text
RespectedBrain/
├── respectedbrain.exe
├── app/
│   └── respectedbrain/resources/
│       ├── vault-template/
│       ├── instructions/
│       ├── skills/
│       ├── integrations/
│       ├── gateway/web/
│       └── defaults.json
└── uninstall/
```

`app/` motorun tek dağıtımını ve bağımlılıklarını içerir. Kaynakta ayrı Python
modülleri vardır; dağıtımda bytecode/arşiv olarak paketlenebilirler. Yukarıdaki
ağaç her modülün düz `.py` dosyası olarak kurulmasını şart koşmaz.

Windows dağıtımı tek klasör halinde paketlenmiş uygulamadır; PyInstaller
onedir, içerik klasörü `app`, kaynaklar `app/respectedbrain/resources` olacak
şekilde kullanılır. Kullanıcı ayrıca Python kurmaz. Inno bu paketi yerleştiren
ince Windows kurucusudur; kendi içinde ikinci Python motoru kurmaz.
Geliştirme ve paket testlerinde aynı Python import paketi kullanılır.

Program çalışırken AppRoot'a config, SQLite, session kaydı, log veya cache
yazamaz. Derlenmiş Python dosyaları dağıtım artifaktıdır; canlı `__pycache__`
oluşturmak için program klasörüne yazma gereksinimi oluşturulmaz.

### 3.2 Kullanıcıya ait teknik veri: DataRoot

Windows varsayılanı: `%LOCALAPPDATA%/RespectedBrain`.

```text
RespectedBrain/
├── config.json
├── install-manifest.json
├── logs/
├── backups/
│   └── <işlem-kimliği>/
│       ├── manifest.json
│       └── önceki sahipli dosyalar
└── vaults/
    └── <vault-id>/
        ├── state/
        ├── cache/
        └── overrides/             # varsa kişisel instructions/skills
```

Bu konum yürütülebilir kod içermez. Birden fazla kasa aynı uygulamayı
kullanabilir; state/cache kasanın kalıcı kimliğiyle ayrılır. Klasörün adı
veya yolun hash'i kasa kimliği olarak kullanılmaz.

- `config.json`: kullanıcı tercihleri, kasa kaydı, aktif kasa ve istenen
  entegrasyon seçenekleri. Paket sürümü burada ikinci doğruluk kaynağı olmaz.
- `state/`: oturum idempotency, son flush/compile/briefing, kilit ve işlem durumu.
- `cache/`: yeniden üretilebilir SQLite indeksleri ve türetilmiş cache.
- `logs/`: kullanıcıya gösterilecek tanılama; MCP/hook protokol stdout'una yazılmaz.
- `backups/`: başarılı geri alma için gereken dosyalar ve işlem günlüğü.
- `install-manifest.json`: uygulamanın yönettiği dosya ve harici kayıt sahipliği.
  Kaynak kod paket manifestiyle aynı şey değildir.

Normal uninstall varsayılan olarak config ve teknik veriyi de korur. Teknik
veriyi kaldırmak ayrı, açık bir seçenek olur; not kasasına hiçbir uninstall
seçeneğiyle dokunulmaz. Cache silinmesi session state silinmesi anlamına gelmez.

### 3.3 Kullanıcı notları: VaultRoot

Varsayılan: `Documents/RespectedOS`; kullanıcı seçimiyle başka yerde olabilir.
Kasa adı uygulama için zorunlu değildir. Geçiş mevcut kasayı taşımaz.

```text
RespectedOS/
├── daily/
├── knowledge/
├── 📥 000-Inbox/
├── 🎯 100-Command-Center/
├── 🏰 300-Projects/
├── 🧠 500-Knowledge/
├── 🛠️ 600-Arsenal/
├── 🔮 850-Companion/
├── 📦 900-Archive/
├── 📋 Templates/
├── .obsidian/
└── .respected.json
```

Kasa kişisel içerik, Obsidian ayarları ve küçük kimlik metadatası içerir.
Motor, Python bağımlılığı, çalışma state'i, arama veritabanı veya kaldırıcı
barındırmaz. Not klasörleri sürüm güncellemesi bahanesiyle yeniden adlandırılmaz.
Kullanıcının kendi kodu veya kendi AI ayarı burada bulunursa kendisine aittir;
geçiş onu dosya uzantısına veya klasör adına bakarak silmez.

`.respected.json` yeni şemada kalıcı UUID `vault_id` ve marker şema sürümü
tutar. Yeni marker'a program yolu veya başka makineye özgü mutlak yol yazılmaz.
Kasanın makine üzerindeki konumu DataRoot/config.json içindeki kayıttadır.
Mevcut marker'ın kimlik bilgileri/ek alanları yedeklenir ve korunur; dönüşüm
bilinmeyen alanları sessizce atmaz.

### 3.4 İşletim sistemi uyarlaması

Windows'ta kullanıcı dizinleri Known Folder API veya onu kullanan ortak
platform resolver üzerinden bulunur; `C:/Users/Furkan` ürüne sabitlenmez.
Documents yönlendirmesi de bu yolla ele alınır.

macOS: AppRoot `~/Applications/RespectedBrain.app`; DataRoot
`~/Library/Application Support/RespectedBrain`.
Linux: AppRoot `~/.local/lib/respectedbrain`, başlatıcı `~/.local/bin/respectedbrain`;
DataRoot `$XDG_DATA_HOME/respectedbrain` veya `~/.local/share/respectedbrain`.
Bu proje config/state/cache'i DataRoot altında alt klasörlerle ayırır;
birden fazla platform kütüphanesi kendi varsayılanıyla ikinci konum oluşturmaz.
Varsayılan kasa sistemin Documents konumu mevcutsa orada, değilse kullanıcı
ana dizininde oluşturulur. Paket CI ilgili platformda çalışmadan o platformun
dağıtımı doğrulanmış olarak yayımlanmaz.

## 4. Kaynak paket ve modüller

```text
secondbrain/
├── pyproject.toml
├── src/respectedbrain/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── core/
│   ├── vault/
│   ├── memory/
│   ├── briefing/
│   ├── search/
│   ├── providers/
│   ├── integrations/
│   ├── gateway/
│   ├── orchestration/
│   ├── maintenance/
│   ├── installation/
│   └── resources/
├── packaging/windows/
├── packaging/macos/
├── packaging/linux/
├── tools/
├── tests/
├── docs/
└── dist/                         # üretilir; kaynak olarak commit edilmez
```

`respectedbrain` import paketi ve `respectedbrain` CLI entry point'i tek
üründür. `python -m respectedbrain` aynı komut dağıtıcısını çağırır.
Kaynak geliştirirken editable paket kurulur; testler normal wheel kurulumu
üzerinde de çalıştırılır. Repo kökünün tesadüfen import edilebilir olması
başarı kriteri değildir. Paket sürümü pyproject metadata'sından okunur;
setup ekranları ve CLI ayrı sabit sürüm tutmaz.

| Modül | Sorumluluk | Sınır |
| --- | --- | --- |
| core | AppPaths, config şeması, ortak hata/işlem sözleşmeleri | Feature modüllerini import etmez |
| vault | Kasa kaydı, kimlik, güvenli not erişimi, not envanteri | Program kurmaz veya sağlayıcı çağırmaz |
| providers | AI CLI çalıştırma, mevcut fallback ve timeout | Kasa temizlemez, global ayar yazmaz |
| memory | Lifecycle, flush, compile, bounded recall, hafıza grafiği | State yolunu kendi başına tahmin etmez |
| briefing | Mevcut brifing akışı | Zamanlayıcı kurulumu yapmaz |
| search | İndeksleme, arama, cache yaşam döngüsü | Veritabanını kasaya yazmaz |
| integrations | Provider olay adaptörleri, MCP, global kayıt, zamanlayıcı | Özellik algoritmalarını ikinci kez içermez |
| gateway | HTTP/panel arayüzü | Dosya temizliği veya doğrudan provider subprocess yönetmez |
| orchestration | Mevcut ajan/worktree yürütme | Kasa ile kod projesini aynı kök kabul etmez |
| maintenance | Yedekleme, linter, onarım, mevcut veri alma araçları | İşlem kapsamı ve hedefi açık olmalıdır |
| installation | Install/update/repair/uninstall/migration koordinasyonu | Not içeriğini paket dosyası saymaz |
| resources | Template, varsayılan talimat/yetenek/entegrasyon tanımları | Canlı config veya state değildir |

Feature modülleri core/vault/providers gibi ortak hizmetleri açık bağlamla
kullanır. Hook/MCP/HTTP arayüzleri bu hizmetleri çağırır. Ortak davranış
CLI betiklerinin birbirini import etmesine bağlı olmaz. Import sırasında
gerçek kasa keşfi, dizin oluşturma, model çalıştırma veya kullanıcı ayarı
yazma yapılmaz. AppPaths ve bağımlılıklar başlangıçta oluşturulup aktarılır.

`tools/` yalnız paket üretimi ve geliştirme araçları içindir. Son kullanıcının
arama, bakım, MCP veya global entegrasyon ihtiyacı buraya taşınmaz.

## 5. Mevcut kaynakların hedef eşleştirmesi

Bu tablo sorumluluk eşleştirmesidir; uygulama sırasında gereken küçük iç
modül ayrımları isimli plan adımlarında yapılır. Yeni feature algoritması
tasarlamak için gerekçe oluşturmaz.

| Mevcut kaynak | Hedef |
| --- | --- |
| runtime/engine/flush.py, compile.py | memory/flush.py, memory/compile.py |
| runtime/hooks/lifecycle.py | memory/lifecycle.py |
| runtime/hooks/bridge.py, codex_notify.py | integrations/hooks/ |
| runtime/session_brain.py, session_viz.py, bounded_recall.py | memory/ |
| runtime/graph_analysis.py, graphrag.py | memory/graph/ |
| runtime/events.py | memory/events.py |
| runtime/map_builder.py | vault/maps.py |
| runtime/model_runner.py | providers/runner.py |
| runtime/morning_briefing.py | briefing/service.py |
| runtime/runtime_hub.py ve scripts/runtime_hub.py | tek core/paths.py |
| runtime/runtime_platform.py | core/platform.py |
| runtime/gateway/server.py ve web/ | gateway/ ve paketlenmiş web kaynakları |
| runtime/orchestrator/runner.py | orchestration/runner.py |
| scripts/orchestrate.py, antigravity_orchestrator.py | orchestration/ içi hizmet ve ince CLI çağrıları |
| scripts/arama.py | search/engine.py |
| scripts/vault_mcp_server.py | integrations/mcp/server.py |
| scripts/install_global.py, install_antigravity_global.py | integrations/global_config/ |
| scripts/install_briefing_schedule.py | integrations/scheduling/ |
| scripts/render_integrations.py | integrations/rendering.py |
| scripts/set_summary_provider.py | core config hizmeti + configure komutu |
| scripts/dashboard.py, dashboard.bat | dashboard komutu; eski giriş ince uyumluluk yönlendirmesi |
| scripts/update_respected.py, auto_updater.py | installation/update.py |
| scripts/migrate_vault_to_runtime.py | installation/migration.py |
| scripts/respected_manifest.py, legacy_names.py | installation/ownership.py, legacy.py |
| installer/install.py, update.py, uninstall.py | installation/ hizmetleri |
| scripts/setup_wizard.py, root setup.py | ortak installation hizmetini çağıran UI/CLI girişleri |
| scripts/install-windows.ps1, root setup/setup.command | packaging altında ince platform başlatıcıları |
| scripts/build_installer.py, upstream_sync.sh | tools/ |
| scripts/backup_restic.py, publish_git_snapshot.py | maintenance/backup/ |
| scripts/repair_daily.py, vault_linter.py, architect_scan.py | maintenance/ |
| scripts/smart_merge.py, tiling_check.py | maintenance/ |
| scripts/mine_agent_history.py, defuddle.py, url_safety.py | maintenance/ingestion/ |
| runtime/instructions.md, skills/ | resources/instructions/, resources/skills/ |
| runtime/adapters/ | kaynak tanımları resources/integrations/; üretilmiş sonuçlar build çıktısı |
| runtime/config.json | resources/defaults.json; gerçek kullanıcı config'i bundan ayrıdır |
| template/ | resources/vault-template/ |
| installer/respected_setup.iss | packaging/windows/respected_setup.iss |
| runtime/state, .state ve __pycache__ | paket dışı; canlı state DataRoot'a aktarılır |
| kökteki setup.exe | dist/ ve release artifaktı; kaynak kopyası olarak tutulmaz |

Eski çalışma ağacındaki henüz commit edilmemiş düzeltmeler her taşınan
dosyanın içeriğinde korunur. Doküman ve test yolu değişiklikleri taşıma
adımıyla birlikte yapılır; bitmiş düzende eski kaynaklarda feature kodu kalmaz.

## 6. Yollar, config ve kasa kimliği

Tek AppPaths bağlamı: app_root, data_root, vault_root, vault_id,
state_dir, cache_dir, log_dir, backup_dir ve paket kaynak erişimi.
Modüller `__file__.parents[n]` veya CWD üzerinden program/veri kökü kurmaz.
Paket kaynakları importlib.resources üzerinden bulunur; çalışma state'i
paket kaynağı olarak açılmaz.

Kasa seçimi: açık `--vault` veya `--vault-id`, ardından açık
`RESPECTED_VAULT_PATH`, ardından config'teki active_vault_id. İki açık
selector birlikte verilirse hata. Açık yol geçersizse başka kasaya fallback
yapılmaz. Config'te kasa yoksa kurulum/registration ister; repo kökünü kasa
saymaz. CWD marker keşfi yalnız `vault discover` gibi açık keşif işleminin
salt okunur davranışıdır, arka plan hook'unun sessiz önceliği değildir.

Yeni `RESPECTED_APP_DIR`/`RESPECTED_DATA_DIR` test ve destek amacıyla açık
override sağlar. Eski `RESPECTED_RUNTIME_DIR` yalnız legacy discovery ve
geçiş girişi olarak değerlendirilir; yeni normal çalışmada app/data'yı tek
yola bağlamaz. Geçersiz eski override tanılama üretir.

Config şeması 3'tür: schema_version, active_vault_id, vaults ve global
preferences/integrations. `vaults` kimlikten konum ve kasa ayarlarına map'tir.
Config atomik yazılır; eşzamanlı güncelleme kayıp veri üretmez.
Paket defaults dosyası kullanıcı config'i üzerine kopyalanmaz.
Geçişte gerçek kullanıcı config'i en yüksek önceliklidir; doğrulanmış legacy
ayarlar eksikleri tamamlar; paket varsayılanları en düşük önceliktedir.
Mevcut summary_provider, provider_priority, kimlik ve entegrasyon tercihleri
korunur. Bilinmeyen legacy alanlar geri alınabilir biçimde saklanır.

Not kasası taşınırsa UUID sabit kalır, yalnız kayıtlı path güncellenir.
Aynı UUID iki farklı kayıtlı klasörde bulunursa uygulama ikinci klasörü
sessizce aynı kasa olarak çalıştırmaz; çakışma bildirilir. Kasa kopyasını
yeni kasa olarak kaydetme UUID değişimini açık işlem olarak yapar.

## 7. Komut, kurulum ve geçiş sözleşmeleri

[Kurulum ve geçiş sözleşmeleri](2026-10-03-modular-foundation-operations.md)
bu tasarımın ayrılmaz parçasıdır. CLI, template davranışı, install/update/
repair/uninstall, legacy migration ve kabul kriterleri bu alt belgede tek
kaynak olarak tanımlanır. Yapısal bölünmede içerik budanmadı.

## 8. Uygulama sırası için bağımlılıklar

[Uygulama planı](../plans/2026-10-03-modular-foundation.md) şu sırayı somut
görev/komut/testlerle açar; planın inceleme durumu kendi belgesindedir:

1. Tek paket, kaynak envanteri ve ortak AppPaths/config/UUID sözleşmesi.
2. Feature kodunun modüllere taşınması ve ortak CLI'a bağlanması.
3. Paket kaynakları/template ve DataRoot state/cache bağlantıları.
4. Entegrasyonların tek başlatıcı ve istenen seçeneklere bağlanması.
5. Ortak install/update/repair/uninstall ve sahiplik manifesti.
6. Önizleme/yedek/rollback içeren legacy migration.
7. Platform paketleri, belgeler, paket testleri ve son devreye alma önizlemesi.

Bu sıra uygulama planının yerine geçmez. Yazılı sözleşme incelendikten
sonra ayrıntılı plan hazırlanır; işlev iyileştirmeleri bundan sonraki iştir.

## 9. Kaynaklar ve karar kaydı

- Kullanıcının 2026-10-03 önce/sonra tasarımını kabul eden mesajı.
- Mevcut kaynaklar: `installer/respected_setup.iss`,
  `runtime/scripts/migrate_vault_to_runtime.py`, `runtime/runtime_hub.py`,
  `runtime/scripts/arama.py`, `runtime/scripts/respected_manifest.py`.
- [Microsoft Known Folders](https://learn.microsoft.com/en-us/windows/win32/shell/knownfolderid):
  kullanıcı program ve uygulama verisi konumları.
- [PyPA src layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/):
  kaynak/import paketi ayrımı.
- [PyPA CLI packaging](https://packaging.python.org/en/latest/guides/creating-command-line-tools/):
  paket entry point'i.

Bu belge yeni hedef sözleşmenin tek kaynak dokümanıdır. Eski
`docs/ARCHITECTURE.md` mevcut/önceki uygulamayı açıklar ve bu belgeye işaret eder.
Vault hafızası hedef ağacı yeniden kopyalamaz; proje notu bu belgeye link verir.

## For future agent

Kullanıcı program/veri/kasa ayrımını ve modüler tek paket yönünü kabul etti.
Yazılı spec onaylandı; uygulama planının incelemesi tamamlanmadan kod taşıma
başlatma; önceki çalışma ağacı düzeltmelerini koru. Canlı kasa
geçişinde yalnız kanıtlanmış sahipli dosyalar üzerinde, yedek ve rollback
ile işlem yap; kullanıcı notlarını veya bilinmeyen kodunu temizleme.
