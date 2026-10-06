> Tarihli karar/işlem kaydı. Eski durum ve komutlar bu tarihin bağlamındadır; güncel yapılacaklar değildir. Bağlantılar ve araç talimatları 2026-10-05 belge düzenine uyarlandı; ham başlangıç kopyası yerel documentation-before ZIP arşivindedir. Eski süreç/klasör adları nötr tanımlara çevrildi; bu tarihsel tanımlar bugünkü dosya yolu değildir. [Aktif durum](../../PROJECT_STATUS.md).

# Modular Foundation Implementation Plan


**Goal:** Mevcut işlevleri koruyarak tek paket ve birbirinden bağımsız program/veri/not kasası yerleşimine geçmek.

**Architecture:** Önce saf paket/yol/config sözleşmesi kurulur, sonra mevcut algoritmalar bu bağlama taşınır. Entegrasyonlar tek CLI'a bağlanır; kurulum ve migration aynı sahiplik, işlem günlüğü ve geri alma hizmetlerini kullanır. Bu tek, sıralı planın görevleri boyut nedeniyle üç ek dosyadadır; ekler bağımsız plan değildir.

**Tech Stack:** Python, stdlib unittest/argparse/importlib.resources/sqlite3, setuptools wheel, PyInstaller onedir, Inno Setup, PowerShell ve POSIX kabukları. Mevcut Python 3.10+ desteği korunur (`requires-python = ">=3.10"`); kaynak/wheel CI 3.10 ve 3.13, frozen build 3.13. Yeni işlev bağımlılığı eklenmez; build araçları geliştirme bağımlılığıdır.

**Spec:** [Ana sözleşme](../../decisions/MODULAR_FOUNDATION.md) ve [kurulum/geçiş sözleşmesi](../../decisions/OPERATIONS.md), kullanıcı onayı 2026-10-03.

scope: project; confidence: verified; supersedes: ["Canlı devreye alma için eski kasanın migration çakışmalarını çözme zorunluluğu", "installer-atlas-platform-staging"]; status: integration-verified, source-cleanup-verified, installer-atlas-platform-verified, source-published, fresh-vault-selected, rollout-deferred-by-user (as of 2026-10-05).

timeline:
  - from: 2026-10-03
    until: 2026-10-03
    learned: "Plan incelemesi ve yöntem seçimi bekleniyordu; kullanıcı karma yöntemi onayladı."
    source: "o zaman öyle yapalım nasıl daha iyiyse bizim için"
  - from: 2026-10-03
    until: 2026-10-04
    learned: "Onaylı plan ayrı çalışma ağacında uygulandı; kaynak ve Windows native doğrulaması tamamlandı."
    source: "VERIFICATION.md"
  - from: 2026-10-04
    until: 2026-10-04
    learned: "Kullanıcı yerel birleştirmeyi onayladı; main dalı 3b45460'a fast-forward ile ilerletildi. Birleşmiş kaynak doğrulaması başladı."
    source: "Kullanıcı: yap onaylıyorum"
  - from: 2026-10-04
    until: 2026-10-04
    learned: "Ana klasörde tam 630 testlik paket OK (15 atlama); test cleanup yarışı düzeltildi ve ayrı worktree kanıtları korunarak arşivlendi."
    source: "VERIFICATION.md#yerel-birleştirme--2026-10-04"

  - from: 2026-10-04
    until: 2026-10-04
    learned: "Önceki durum source-cleanup-gaps idi; onaylı son temizlik eski girişleri kaldırdı ve yayın tarifini native build sözleşmesine bağladı."
    source: "../2026-10-source-cleanup/VERIFICATION.md"

  - from: 2026-10-04
    until: 2026-10-04
    learned: "Önceki devreye alma yolu live-migration-conflicts idi; kullanıcı eski kasayı en son yedekleyip ZIP'leyerek sıfırdan yeni kasa seçti."
    source: "Kullanıcı: eski kasayı yedekleyip zipleyip yeni kasaya geçicem zaten sıfırdan ... en son yapcam onu"

  - from: 2026-10-04
    until: 2026-10-05
    learned: "Kurulum seçimleri/hız, 271 dosyalık atlas ve sekiz ölü hook temizliği çalışma dalında; gerçek platform CI son fixture düzeltmelerini doğruluyor. Önceki integration/source-cleanup durumu korunur; GitHub main henüz ilerletilmedi."
    source: "../2026-10-installer-release/EXECUTION.md; CI run 37234992142"

## CI sonuçlarının kullanıcı çağrısıyla incelenmesi — 2026-10-05

Kapanış kaydı: `631c37e` kaynak commit'i için [37318525236 CI koşusunun](https://github.com/respected0/respectedbrain/actions/runs/37318525236)
12/12 işi başarılı. Üç native platform ve üç host × iki Python source kapısı
doğrulandı; önceki staging durumu bu kanıtla kapandı. `main`, onaylı çalışma
dalına fast-forward ile ilerletildi; birleşmiş ana klasörde 19 recovery/atlas
testi ve 271 dosya atlas kontrolü geçti. Kapanış belgeleri ürün kodunu değiştirmez.
Canlı kurulum/kasa geçişi kullanıcının sonraki aşamasıdır. Önceki geçici ağacı
koruma gerekçesi, kullanıcının 2026-10-05 temizlik isteğiyle giderildi: global
Python 3.13 ve iki izole 3.10 editable bağlantısı ana projeye yönlendirildi,
2.148 ignored kanıt/derleme dosyası SHA256 eşleşmesiyle korundu ve managed
installer-atlas çalışma ağacı geri yüklenebilir biçimde arşivlendi. Arşiv
sonrasında dört Python ortamının import/CLI kontrolü ana kaynakta geçti.
Ayrıntılı kanıt devam planındadır; kaynak çalışma kökü ana secondbrain klasörüdür.
Arşivden kalan boş dizinin ilk kaldırma girişimi Windows süreç kilidine
takıldı. Kullanıcı eski projeyi/terminali kapattıktan sonra boş dizin de
kaldırıldı; hedef yol artık yok, Git listesinde yalnız ana checkout var.

scope: project; confidence: verified; supersedes: ["Push sonrası otomatik CI bekleme/sorgulama varsayımı"]

Kullanıcı push sonrasında sürekli GitHub CI sorgulayarak beklemeyi istemiyor.
Kod incelemesi ve ilgili yerel doğrulama tamamlandıktan sonra çalışma dalı
gönderilir ve tur biter. CI sonucu çıktığında kullanıcı yeniden çağırır;
o çağrıda gerçek sonuç değerlendirilir. Bekleme ajanı/otomasyonu başlatılmaz.
Main birleştirmesi için gerçek son platform kapılarının başarı şartı korunur.

## Kullanıcının devreye alma kararı — 2026-10-04

Eski kasa kullanıcı tarafından en son yedeklenip ZIP arşivine alınacak; ardından
sıfırdan yeni boş kasa oluşturulacak. Yeni kasaya eski health/session state,
cache veya not aktarımı varsayılmayacak. Yeni kasa kendi UUID'si ve ona bağlı
teknik state/cache alanıyla başlayacak. Kurulum ve kasa değişimi son aşamadadır;
bu karar mevcut kasayı ZIP'leme, silme, taşıma veya ürün kurma talimatı değildir.

Eski health.json/session_start_time çakışmaları eski veriyi içeri aktaran
migration yoluna aittir; bu kullanıcı için yeni kasa açmanın önkoşulu değildir.
Codex computer-use notify zinciri kasa verisinden bağımsız program bağlantısıdır;
son kurulumda iki bağlantı da korunarak yeniden düzenlenmesi gerekir.
Eski AppData ayarlarını veya teknik verileri silme/sıfırlama izni varsayılmaz;
eski program/veri köklerinin yeni kurulumla birlikte nasıl ele alınacağı son
kurulum öncesi hazırlanır. Migration özelliği ve mevcut kasa koruma sözleşmesi
diğer kullanım durumları için üründe kalır.

Yürütme: ortak paket/yol/config/UUID temelini ana ajan kurar; temel oturunca
iki bağımsız iş akışı paralel ajanlara verilir; sonuçlar birleştirilip ayrı
ajanla son inceleme yapılır. Aynı dosyada eşzamanlı düzenleme yapılmaz.

## Yürütme sonucu — 2026-10-04

Görev 1–13 uygulandı ve doğrulandı. [Test ve canlı envanter kanıtı](VERIFICATION.md)
627 kaynak testi (15 gerekçeli atlama), gerçek Windows kurucu/güncelleme/kaldırma,
launcher/zamanlayıcı ve 17 kontrolün tamamını geçen fiziksel smoke sonuçlarını içerir.
Linux/macOS/gerçek WSL fiziksel doğrulaması bu yerel çalışmada yoktur.

Önceki aktarım yolunda görev 14'ün salt okunur önizlemesi ve devreye alma kapısı değerlendirildi.
Health/session state farkları ve Codex computer-use notify zinciri sahipliği nedeniyle
gerçek apply yapılmadı. Not kasası mevcut konumundadır. Onaylanan yerel birleştirmeyle
kod artık `Documents/ChatGPT/secondbrain` klasöründeki `main` dalındadır. Birleşmiş
kaynağın tam 630 testlik paketi başarılıdır (15 gerekçeli atlama). Başlangıçtaki 41 dosya
düzenlemesi yeni çalışmaya önceden taşınmıştı; birebir byte yedeği ve Git stash ayrıca
korunur. Ayrı managed worktree, gerekli paketler ve kanıtlar ana projeye kopyalandıktan
sonra arşivlendi.
Eklerdeki kontrol listeleri uygulama tarifidir; güncel yürütme durumu
yalnız bu bölümde tutulur.

## Kaynak yerleşimi incelemesi ve son temizlik — 2026-10-04

Aşağıdaki gözlemler temizlik öncesinin tarihsel kaydıdır. Kullanıcının son temizliği
onaylamasıyla eski kaynak ağacı ve setup girişleri kaldırıldı; release akışı
native build/verify/test/smoke araçlarına bağlandı. 629 testlik paket OK
(15 atlama), wheel/sdist ve gerçek Windows native paket doğrulaması başarılıdır.
[Son kaynak temizliği doğrulaması](../2026-10-source-cleanup/VERIFICATION.md) işlemleri ve
tarihli kanıtı kaydeder. Gerçek ürün kurulumu uygulanmadı. Eski migration önizlemesinin çakışmaları
tarihsel kanıttır; güncel kullanıcı yolu yukarıdaki devreye alma kararındadır.

Kullanıcının hedef ağaç ile mevcut klasörü karşılaştırması üzerine salt okunur
denetim yapıldı. Önceki uygulama/test kanıtı korunur; bunun bütün eski kaynak
kopyalarının ve yayın akışlarının temizlendiği anlamına geldiği yorumu düzeltilir.

timeline:
  - from: 2026-10-04
    until: 2026-10-04
    learned: "Önceki durum implementation-verified idi; kaynak yerleşiminin son temizliği aşağıdaki açıklarla tamamlanmamış bulundu."
    source: "runtime/adapters/, runtime/gateway/web/index.html, .github/workflows/release.yml salt okunur incelemesi"

- `runtime/` ve `installer/` altındaki Python girişlerinin çoğu yeni pakete ince
  yönlendirmedir. Plan yalnız bir geçiş sürümü için bunlara izin verir.
- `runtime/adapters/` altındaki eski skill/talimat/hook içerikleri ve
  `runtime/gateway/web/index.html` yalnız yönlendirme değildir; eski içerik
  kopyaları kalmıştır. Yeni paket kaynakları `src/respectedbrain/resources/` olur.
- `.github/workflows/release.yml` macOS/Linux için kaldırılmış `template/` ile
  eski `runtime/installer` ağacını kopyalar; Windows için eski kök `setup.exe`
  çıktısını bekler. Yayın akışı yeni native build sözleşmesine uyarlanmamıştır.
  Bu inceleme workflow çalıştırması değildir; mevcut komutlar kaynakta doğrulandı.
- İnceleme sırasında kaynak temizliği ve release uyarlaması açık işti.
  Sonraki onaylı temizlik bu kaynak açıklarını kapattı. Canlı migration ayrı iştir.

## Global Constraints

- Windows AppRoot: `%LOCALAPPDATA%/Programs/RespectedBrain`.
- Windows DataRoot: `%LOCALAPPDATA%/RespectedBrain`.
- Varsayılan VaultRoot: `Documents/RespectedOS`; mevcut kasa taşınmaz.
- macOS AppRoot: `~/Applications/RespectedBrain.app`; DataRoot: `~/Library/Application Support/RespectedBrain`.
- Linux AppRoot: `~/.local/lib/respectedbrain`; launcher: `~/.local/bin/respectedbrain`; DataRoot: `$XDG_DATA_HOME/respectedbrain` veya `~/.local/share/respectedbrain`.
- Windows Known Folders ve Documents yönlendirmesi kullanılır; kullanıcı adı sabitlenmez.
- Tek `respectedbrain` paketi, tek CLI, tek aktif motor; Windows kullanıcıya Python kurdurmaz.
- PyInstaller onedir içerik klasörü `app`; kaynaklar `app/respectedbrain/resources`.
- Program çalışırken AppRoot'a teknik veri yazılmaz; DataRoot yürütülebilir ürün kodu içermez.
- Config ve marker şeması `3`; kalıcı kasa UUID'si yol hash'i değildir.
- Kasa seçimi: açık `--vault`/`--vault-id`, `RESPECTED_VAULT_PATH`, `active_vault_id`.
- İki selector hata; açık geçersiz selector başka kasaya fallback yapmaz.
- `RESPECTED_APP_DIR`/`RESPECTED_DATA_DIR` açık override; `RESPECTED_RUNTIME_DIR` yalnız legacy girişidir.
- Import sırasında keşif, mkdir, kullanıcı config okuma/yazma veya subprocess çalıştırma yapılmaz.
- core feature import etmez; özellikler CLI modülünü import etmez.
- Paket defaults kullanıcı config'inin üzerine kopyalanmaz; config atomik ve kayıp güncelleme olmadan yazılır.
- Kullanıcı config'i > geçerli legacy tercihler > paket defaults; bilinmeyen alanlar korunur.
- Instructions/skills kişiselleştirmeleri UUID'ye bağlı `overrides/` altında korunur.
- Global/MCP/zamanlayıcı yalnız desired-state ile açılır; kapalı seçenek kapalı kalır.
- Hook/MCP stdout protokol içindir; tanılama stderr/DataRoot logs kullanır.
- Migration varsayılan dry-run; değişiklik için `--apply` gerekir.
- Bilinmeyen dosyalar kullanıcıya aittir; temizleme manifest ve değişmemiş hash ister.
- Güncelleme/onarım/kaldırma kullanıcı notlarını ve `.obsidian` dosyalarını değiştirmez.
- Uninstall DataRoot'u varsayılan korur; açık `--purge-data` bile kasaya dokunmaz.
- Inno AppId `{870D0E4C-87A0-4A3C-9A82-F8E3C3A19C1D}` korunur; `UsePreviousAppDir=no`; uninstaller `AppRoot/uninstall`.
- Eski geniş temizlik yapan uninstaller çalıştırılmaz; rollback başka ajanın yeni dosyasını silmez.
- Önceki çalışma ağacı düzeltmeleri taşınan güncel dosyalarda korunur.
- Yeni ürün özelliği, portable/system-wide kurulum, mikroservis veya plugin yöneticisi eklenmez.
- Canlı kurulum ancak geçici kasa ve paket kontrollerinden sonra, son devreye alma adımında ele alınır.

## Review Focus

1. Türkçe/emoji/boşluklu yol, yönlendirilmiş Documents, yanlış CWD ve iki kasa: doğru UUID seçilir, geçersiz açık seçim hata verir. Görev 2–3.
2. Kasa taşınması/kopyalanması ve iki süreçten config güncellemesi: UUID korunur, kopya çakışır, iki değişiklik de kalır. Görev 3.
3. Kapalı global/MCP/schedule, özel provider tercihi ve değiştirilmiş instructions/skills: geçiş bunları korur. Görev 8, 11–12.
4. State çakışması, aktif yazıcı, junction/symlink ve sahipli dosyanın envanterden sonra değişmesi: etkinleştirme durur, bilinmeyen dosya korunur. Görev 9, 11–12.
5. Her işlem aşamasında hata ve Windows'ta kullanımda executable: geri alma kanıtlanır; not hash'leri ve eşzamanlı kullanıcı dosyaları korunur. Görev 10, 12–13.

---

## Kullanıcı için uygulama sırası

1. **Görev 1–3:** Tek paket, ortak yollar ve kasa kimliği.
2. **Görev 4–7:** Şu anki işlevlerin yeni modüllere taşınması ve tek komut.
3. **Görev 8–10:** AI bağlantıları, kurulum, güncelleme ve kaldırma.
4. **Görev 11–13:** Eski kurulumun güvenli dönüşümü ve gerçek dağıtım paketi.
5. **Görev 14:** Gerçek bilgisayarda önce önizleme, sonra denetlenen devreye alma.

## Dosya haritası

Tüm yollar repo köküne göredir. Kaynak→hedef envanteri spec §5'tir; burada
tam hedef dosya adları ve sahip görevler sabitlenir. Taşınan dosyanın güncel
disk içeriği kullanılır; eski commit'ten içerik alınmaz.

| Görev | Yeni/değişen dosyalar ve sorumluluk |
| --- | --- |
| 1 | `pyproject.toml`, `src/respectedbrain/{__init__,__main__,cli}.py`: metadata/dispatcher; `core/resources.py`: salt okunur kaynak erişimi; `resources/`: template, defaults, instructions, skills, integrations, gateway/web; `tests/foundation_support.py`: geçici kasa ve hash yardımcıları; `tests/package_contract_test.py`: wheel/import sınırı |
| 2 | `core/{paths,platform,context,errors}.py`: saf yol/bağlam/hata; `tests/foundation_paths_test.py` |
| 3 | `core/config.py`, `vault/registry.py`: kilitli config ve UUID kaydı; `tests/vault_registry_test.py` |
| 4 | `providers/runner.py`; `memory/{flush,compile,lifecycle,session_brain,session_viz,bounded_recall,events}.py`, `memory/graph/{graph_analysis,graphrag}.py`; `tests/foundation_memory_test.py` |
| 5 | `briefing/service.py`, `search/engine.py`, `vault/maps.py`; `tests/foundation_features_test.py` |
| 6 | `gateway/server.py`, `orchestration/{runner,orchestrate,antigravity_orchestrator}.py`; `maintenance/{repair_daily,vault_linter,architect_scan,smart_merge,tiling_check}.py`; `maintenance/backup/{backup_restic,publish_git_snapshot}.py`; `maintenance/ingestion/{mine_agent_history,defuddle,url_safety}.py`; `tests/foundation_services_test.py` |
| 7 | `cli.py`, `bootstrap.py`: tek composition root/komutlar; `tests/foundation_cli_test.py` |
| 8 | `integrations/hooks/{bridge,codex_notify}.py`, `integrations/mcp/server.py`, `integrations/{global_config,legacy_registration}.py`, `integrations/scheduling/service.py`, `integrations/{rendering,backend}.py`; `tests/foundation_integrations_test.py` |
| 9 | `installation/{ownership,transaction,setup,wizard}.py`; `tests/foundation_setup_test.py` |
| 10 | `installation/{update,repair,uninstall}.py`; `tests/foundation_operations_test.py` |
| 11 | `installation/{legacy,migration}.py`; `tests/foundation_migration_preview_test.py` |
| 12 | `installation/migration.py`; `tests/foundation_migration_apply_test.py` |
| 13 | `packaging/windows/{respectedbrain.spec,respected_setup.iss,install.ps1}`, `packaging/macos/setup.command`, `packaging/linux/setup.sh`; `tools/{build_installer.py,upstream_sync.sh,verify_distribution.py}`; `.github/workflows/{ci,release}.yml`; `tests/foundation_distribution_test.py`; mevcut smoke/native/PS1/shell testleri; README ve rehberler |
| 14 | Yeni ürün kodu yok; kullanıcıya sunulan canlı envanter, backup ve doğrulama raporu |

Her paket alt dizininde yan etkisiz `__init__.py` bulunur. `runtime/instructions.md`
→ `resources/instructions/default.md`; `runtime/config.json` → `resources/defaults.json`.
`runtime/adapters/` kaynak tanımları → `resources/integrations/`; üretilmiş provider
ayarları paket kaynak tanımıyla karıştırılmaz. `runtime/scripts/enable_multiai.py`
→ görev 8'de rendering/global_config hizmetlerine delegasyon; yeni algoritma yok.
`setup.py`, `setup`, `setup.command`, `installer/*.py` ve eski doğrudan CLI
dosyaları yalnız bir geçiş sürümü için ince yönlendirme olabilir; ürün mantığı
hedef dosyalarda kalır. `runtime_hub.py` kopyalarının yerine yalnız `core/paths.py`
geçer. Kökteki `setup.exe` source control'den çıkar; yeni çıktı `dist/` olur.

## Ortak doğrulama ve çalışma disiplini

Uygulama başlangıcında `using-git-worktrees` ile izolasyon oluştur. Şu anki
kirli çalışma ağacı için önce `git status --short`, `git diff --binary` ve
`tests/runtime_layout_test.py` içeriğini güvenli workspace snapshot'ına al.
Yeni worktree'ye takip edilen diff'i `git apply` ile ve takip edilmeyen testi
birebir kopyalayarak aktar; hash/diff karşılaştır. Ana checkout'u resetleme.
Bu taban doğrulanmadan taşıma başlatma. Üretilmiş mevcut `setup.exe` kaynak
olarak yeniden üretimde kullanılmaz; snapshot'ta korunur.

PowerShell'de `$py` ve `$pwsh` gerçek çalıştırıcıya atanır. Bu makinede Python:
`C:/Users/Furkan/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`.
Yeni worktree'de `.venv` oluştur ve `$py` değerini `.venv/Scripts/python.exe`
yap; POSIX eşdeğeri `.venv/bin/python`. CI `python` kullanır.

Başlangıç: `& $py -m unittest discover -s tests -p '*test*.py'` çıktısını kaydet;
önceki 447/10 tarihsel ölçümdür, yeni koşuda aynı sayı zorunlu değildir.
Her görevde yeni anlamlı test önce FAIL, sonra OK olur; regresyon modülleri
aynı davranışı paket importlarıyla sınar. Eski konumun varlığını bekleyen
testler yeni sözleşmeye çevrilir; davranış testi sırf taşıma için silinmez.
Her commit'te yalnız o görevin dosyalarını stage et, `git diff --cached --check`
çalıştır; `git add .` kullanma.

`tests/foundation_support.py` sadece stdlib kullanır:
`snapshot(root: Path) -> dict[str, str]` dizin/symlink/dosya SHA256 envanteri;
`note_hashes(vault: Path) -> dict[str, str]` daily, knowledge, Companion,
proje, Templates, `.obsidian` dosyaları; `write_json(path: Path, value: dict) -> None`;
`run_cli(argv: list[str], *, env: dict[str,str], cwd: Path) -> CompletedProcess[str]`.
Test sınıfları TemporaryDirectory içinde `app`, `data`, `Türkçe 🧠 Vault`,
`İkinci Vault` yollarını oluşturur; gerçek HOME/AppData/provider config/task
kullanılmaz. Gerçek native kayıt testleri yalnız geçici kullanıcı dosyası ve
benzersiz task adıyla, finally temizliğiyle çalışır.

## Görevlerin uygulanması ve temel sözleşmeler

Görev 1–13'ün kaynak/paket çalışmaları ve görev 14'ün salt okunur önizlemesi [doğrulama raporunda](VERIFICATION.md) kayıtlıdır. Görev 14'ün gerçek canlı kurulumu uygulanmadı. Kaldırılan üç ayrıntılı görev planının ham metni `.local/archives/docs-cleanup-baseline-2026-10-05.zip` içinde korunur; aşağıdaki özet onların tüm adım ve örneklerini tekrar etmez.

- **Görev 1–3 (Temel, Yol, Config):** `ResourceCatalog`, `Roots`, `AppPaths`, `AppContext`, `ConfigStore`, `VaultRegistry` ile bağımsız AppRoot/DataRoot/VaultRoot ayrımı ve kalıcı UUID kasa kimliği kuruldu.
- **Görev 4–5 (Hafıza, Arama, Brifing):** `ModelRunner`, `compile_memory`, `flush_transcript`, `SearchEngine` ve `run_if_due` bağlam altına taşındı; veri izolasyonu sağlandı.
- **Görev 6–7 (Servisler, CLI):** `gateway/server`, `orchestration/runner`, `maintenance` araçları ve tek composition root `bootstrap.py` üzerinden dispatch eden `cli.py` tamamlandı.
- **Görev 8–10 (Entegrasyonlar, Kurulum İşlemleri):** `IntegrationBackend`, `plan_integrations`, hook köprüsü, `OwnershipManifest` ve `Transaction` ile geri alınabilir `setup`, `update`, `repair`, `uninstall` işlemleri kuruldu.
- **Görev 11–13 (Migration ve Dağıtım):** `inventory_legacy`, `plan_migration`, `apply_migration`, `tools/build_installer.py`, `tools/verify_distribution.py` ve native CI paketleme akışı tamamlandı.
- **Görev 14 (Devreye Alma):** Salt okunur önizleme doğrulanmış; gerçek canlı geçiş kullanıcının [devreye alma kararına](#kullanıcının-devreye-alma-kararı--2026-10-04) ve yerel `.local/ROLLOUT.md` kaydına bırakılmıştır.

## Plan öz incelemesi

Spec §1–5 → görev 1, 4–6, 13; §6 → görev 2–3; §7/operations §1 → görev
7–8; operations §2–3 → görev 9–10; operations §4 → görev 11–12; operations
§5 → görev 13–14. Beş Review Focus koşulunun sahip testleri eklerde isimli
assertion'larla bulunur. Kaynakların tamamı dosya haritasında/spec eşleştirmesinde
bir göreve atanmıştır; `enable_multiai.py` envanterde ayrıca kapatılmıştır.
İmzalar ortak AppPaths/AppContext ve isimli sonuç tipleriyle tutarlıdır.
Öz incelemede olmayan `repair_daily --check` seçeneği kaldırıldı; mevcut
salt okunur `vault_linter --json` kullanıldı. Python sürüm tabanı mevcut
README'deki 3.10+ ile eşlendi, sürüm tabanı yükseltilmedi.

## For future agent

2026-10-04 kurulum seçenekleri/hız, eksiksiz dosya atlası, kaynak denetimi ve
GitHub platform doğrulaması için [devam planını](../2026-10-installer-release/EXECUTION.md)
oku. Bu devam işi canlı kullanıcı kurulumunu veya kasayı değiştirmez; kişisel
devreye alma tercihi Git dışındaki `.local/ROLLOUT.md`, aktif ürün durumu
[PROJECT_STATUS](../../PROJECT_STATUS.md) içindedir; bu plan tarihli kayıttır.

Spec ve karma yürütme yöntemi kullanıcı tarafından onaylandı. Tamamlanan görevleri
yeniden uygulama; aktif işi PROJECT_STATUS ve mevcut kullanıcı talimatından al.
Canlı kurulum değişikliğine görev 14'ün önizleme ve geri alma kontrolleri
tamamlanmadan geçme.
