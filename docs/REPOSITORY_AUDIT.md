# Kaynak deposu denetimi — 2026-10-04

scope: project; confidence: verified; supersedes: []

Bu denetim `installer-atlas` worktree'sinin kaynak dosyalarını kapsar. Canlı
RespectedOS kasası, kullanıcı profillerindeki sağlayıcı ayarları ve canlı kurulum
değiştirilmedi. Dosya görevlerinin fihristi [depo haritasında](REPOSITORY_MAP.md)
tutulur. Bu belge bulgular ve doğrulama sınırları içindir.

## Kapsam ve yöntem

- Başlangıçtaki **270 takip edilen dosyanın tamamı**, toplam 1.803.337 byte,
  UTF-8 olarak okunup içerik/yol/uzantı/hash denetiminden geçti. Sonradan eklenen
  atlas ve test dosyaları bu başlangıç sayısına dahil değildir.
- **152 Python dosyasının** AST ayrıştırması başarılı; paket içindeki **82 Python
  modülünün** statik iç import hedeflerinde bulunamayan modül yok.
- JSON ve Canvas kaynaklarının ayrıştırmasında hata yok. `pyproject.toml`
  package-data listesi takip edilen Python dışı paket kaynaklarıyla tam eşleşir:
  eksik paket kaynağı veya artık bulunmayan listelenmiş dosya yok.
- Tarihsel arşiv hariç Markdown göreli bağlantıları URL decode edilerek hedef
  varlığı açısından kontrol edildi. Aşağıdaki düzeltmeler sonrası eksik hedef yok.
- Tüm takip edilen içerikte özel anahtar başlığı, uzun GitHub/OpenAI token biçimi
  ve AWS erişim kimliği için aday taraması yapıldı; eşleşme bulunmadı. Bu tarama
  bütün olası sır biçimlerini veya Git geçmişini doğrulamaz. Sır içerikleri araç
  çıktısına yazılmadı.
- Kaynak, kurulum/release tarifleri, güncel rehberler, sağlayıcı argv politikası,
  SSRF transport'u, snapshot guard ve test izolasyonu ayrıca anlam bakımından
  incelendi. Her dosyanın bütün davranışının doğrulandığı iddia edilmez.

## Düzeltilen bulgular

| Bulgu | Kanıt ve değişiklik |
| --- | --- |
| IDE artık olmayan motor yollarını kullanıyordu | `.vscode/settings.json` içindeki `./scripts` ve `./template/.beyin/*` analysis yolları mevcut `./src` ile değiştirildi. |
| Yeni kasa Dashboard bağlantıları yanlış klasöre gidiyordu | `🎯 100-Command-Center/Dashboard.md` içindeki Capture/Projeler/Bilgi yolları aynı klasörde arama yapıyordu; hedefler doğrulanarak `../` eklendi. |
| Güvenlik politikası kaldırılmış script adlarını ve uygulanmayan garantileri taşıyordu | `docs/SECURITY.md` güncel modüllere yönlendirildi. Sağlayıcı izin farkları, staging'in OS sandbox olmaması, DNS adresinin bağlantıya sabitlenmemesi ve package hash'inin yayıncı imzası olmaması açıklandı. |
| Eski platform kanıtı güncel native ürün kanıtı gibi okunabiliyordu | `docs/TEST-MATRIX.md` 2026-09-14 kanıtını tarihsel olarak işaretler ve güncel tarihli raporlara link verir. Eksik `MANUAL-ACCEPTANCE-0.0.1.md` bağlantısı mevcut smoke rehberine yönlendirildi. Eski test sonuçları silinmedi veya güncel test sonucu olarak yeniden yazılmadı. |
| Template ignore yorumu kaldırılmış bir korumayı vaat ediyordu | `vault-template/.gitignore` başındaki `assert_no_secret_staged` iddiası çıkarıldı. Ignore kuralları değişmedi; önceden takip edilen dosyalar ve not gövdesindeki sırlar için sınırlama belirtildi. |
| Wheel izolasyon testi kaynak `PYTHONPATH` ile yanlış sonuç veriyordu | `tests/package_contract_test.py`: `pip --python` kaynak egg-info'sunu görünce aynı sürümü zaten kurulu sayabiliyordu. Sonraki temiz probe `ModuleNotFoundError` veriyordu. Venv/pip/probe ortamlarından `PYTHONPATH` ve `PYTHONHOME` çıkarıldı. Aynı 32 test temiz ortamda önce geçti; kaynak `PYTHONPATH` ile ilk koşu aynı probe'da başarısız oldu. |

Paket kaynakları değiştiğinden son native dağıtım bu içerikle yeniden üretilmelidir.
Mevcut kullanıcı notları güncellenmiş başlangıç şablonuyla üzerine yazılmaz.

## Davranışta kalan sınırlar ve öneriler

### Web alımında DNS rebinding sertleştirmesi

`maintenance/ingestion/defuddle.py:178` URL/DNS doğrulaması yapar; `:191` normal
`urllib` opener ile hostname'e bağlanır. `url_safety.py` doğrulanmış IP'yi
transport'a iletmez. DNS'in bu iki adım arasında değişmesi halinde özel adrese
bağlantı mümkün olabilir; bu audit gerçek bir rebinding saldırısı çalıştırmadı.
Mevcut `scripts_test.py` ve `zero_trust_security_test.py` URL/DNS filtrelerini
sınar; peer IP pinning ve proxy ile bağlantı garantisi sunmaz.

**Öneri:** Ayrı bir davranış değişikliği olarak güvenli transport geliştirin;
doğrulanmış public IP'ye bağlantıyı sabitleyin, HTTPS hostname doğrulamasını
koruyun, yönlendirme/proxy politikasını ve bağlantı anındaki DNS değişimini
adversarial testlerle sınayın. Yalnız açıklama bu güvenlik açığını kapatmaz.

### Sağlayıcı süreçleri eşdeğer sandbox kullanmıyor

`providers/runner.py:83–160` içinde Codex read-only/workspace-write kullanır;
Antigravity `--dangerously-skip-permissions`, Cursor workspace `--force`, Gemini
workspace `auto_edit` kullanır. Cursor/Gemini text modu uygulama tarafından açık
araç kapatma/sandbox bayrağı almaz. `0700` staging dizini aynı kullanıcıya ait
sağlayıcı sürecini bütün dosya sisteminden yalıtmaz. Staging terfi kontrolü
uygulamanın terfisini sınırlar; sağlayıcının dış dosyalara bağımsız erişimini
engellediği iddia edilemez.

**Öneri:** Sağlayıcı başına gerçek CLI sürümü/izin sözleşmesini ayrı doğrulayın;
untrusted derleme için minimum erişim politikası tasarlayın. Mevcut sağlayıcı
davranışı bu audit'te değiştirilmedi.

### Git snapshot guard eksiksiz secret tarayıcısı değil

`maintenance/backup/publish_git_snapshot.py:55–75` yalnız belirli dosya adı
kalıplarını kontrol eder; `:184` `git add .` çalıştırır. Geçici ve tamamen
sentetik fixture'da `auth.json`, `token.json` ve parola benzeri not gövdesi
guard'dan **`(True, [])`** aldı. Template ignore yeni auth/token dosyalarını
dışlar; önceden takip edilen dosyalar ignore'a rağmen güncellenebilir. Mevcut
`backup_and_snapshot_test.py` ve `zero_trust_security_test.py` bazı filename
guard'larını ve divergence davranışını sınar, bu içerik/staged-file sınırını
kapatmaz. Önizlemede dal kontrolü için `git fetch` yapılabilir.

**Öneri:** Yayından önce gerçek Git index/candidate kümesini ve hassas dosya
kalıplarını doğrulayın; not içeriği için uygun secret taraması ekleyin. Bu
isteğe bağlı yayın aracının davranışı bu audit'te değiştirilmedi.

### Release güven zinciri

`installation/payload.py` manifestteki SHA-256 ve yolları doğrular. Manifest
ile payload birlikte değiştirilirse yayıncı kimliği kanıtlanmaz.
`tools/build_installer.py` ve `.github/workflows/release.yml` içinde code-signing,
macOS notarization veya ayrı imzalı release attestation adımı yok. Workflow
tag/sürüm eşleşmesini, üç native build'i, frozen doğrulamasını, full suite'i
ve platform smoke'u yayın öncesi zorunlu kılar; bu kapılar kaynak kimliği
doğrulaması yerine geçmez.

**Öneri:** Dağıtım hedeflerine göre imzalama/notarization ve doğrulanabilir
provenance ayrı yayın işi olarak ele alınabilir. Audit uzak workflow çalışması
ve Apple/Windows yayıncı sertifikalarını doğrulamadı.

## Silme kararı

Bu audit **kanıtlanmış sekiz ölü hook kaynağını** kaldırdı:
`resources/integrations/.claude/hooks/` içindeki `lib.sh`, `post-compact.sh`,
`pre-compact.sh`, `prompt-counter.sh`, `session-end.sh`, `session-start.sh`,
`session-stop-capture.ps1`, `session-stop-capture.sh` ve bunların package-data
girdileri. Modern `.claude/settings.json` UUID seçen `respectedbrain hook`
komutlarını kullanır; `render_project_integrations` yalnız beş JSON template'i
okur. Kaynak/test/packaging taramasında bu wrapper'ları okuyan tüketici yoktur.
Legacy inventory paket baseline'ı olarak yalnız instructions/skills okur;
eski kullanıcı hook yollarını inceleyen ownership kodu korunur. Beş wrapper
artık paketlenmeyen `.beyin/hooks/bridge.py` dosyasını hedefliyordu. Silme tam
dosya yollarıyla yapıldı; tarihsel metinler veya canlı kullanıcı hook'ları
hedeflenmedi. Diğer ürün dosyaları için kanıtlanmış gereksizlik bulunmadı.
Önceki kaynak temizliğinin kaldırdığı `runtime/installer/template` girişleri
zaten mevcut değildir. Migration kodu eski canlı kurulumları okumak için
kullanılır; legacy isimlerin her geçişi ölü dosya kanıtı değildir.

Exact hash eşleşmeleri şu meşru gruplarla sınırlı:

- Paket `__init__.py` gövdeleri: paket sınırları olarak gerekir.
- AGENTS/CLAUDE/Gemini/.agents instruction girişleri: farklı sağlayıcı kurulum
  hedefleri; kanonik instruction'a yönlendiren küçük kaynaklar.
- Linux/macOS/WSL smoke shell girişleri: kullanıcı/CI için ayrı platform adları.
- `.gitkeep` dosyaları: başlangıç kasasının boş dizin sözleşmesi; package-data
  listesine dahildir ve silinirse seed yapısı değişir.

`docs/history/`, eski tasarım/uygulama/kanıt notları ve ignored `.superpowers`
içindeki recoverable yedekler korunur. `build/`, `dist/`, egg-info ve
`__pycache__` üretilen yerel çıktıdır; kaynak veya kullanıcı notu sayılmaz.
Root hidden metadata `.github`, `.vscode`, `.gitattributes`, `.gitignore` ve
worktree `.git` pointer'ından oluşur; tracked kişisel `.env/.aws/.codex`
ayar dosyası bulunmadı.

## Performans kanıtı

Ana işçi aynı **1065 dosyalı Windows native payload** üzerinde geçici kurulum
ile cProfile açık ölçüm yaptı: önce **173.833 s**, sonra **53.086 s**;
profil koşulunda **%69,5 azalma / 3,27x hızlanma**. Journal snapshot sayısı
2318'den 1202'ye indi. Schema 3, compare-and-swap hash'leri, byte yedekleri,
mode ve fsync sözleşmesi korundu. İlgili test sonuçları ana doğrulama raporuna
aittir. Bu ölçüm canlı kullanıcı kurulumunun duvar saati süresi için vaat
değildir; profiling overhead'i, disk ve işletim sistemi koşulları etkiler.

## Doğrulama sınırı

Audit sırasında başlangıç kaynak AST/JSON/import/resource ve göreli link
kontrolleri geçti; audit değişikliklerinin `git diff --check` kontrolü temiz.
Dar regresyon komutu `foundation_packaged_commands_test`, `package_contract_test`,
`source_cleanup_test`, `zero_trust_security_test`, `backup_and_snapshot_test`
modüllerini kapsar. İlk wheel build yazımı sandbox izniyle durdu; izinli koşuda
kaynak `PYTHONPATH` test sorunu yeniden üretildi. Temiz ortamda **32 test /
13.517 s / OK** ile ortam nedeni ayrıştırıldı. Test düzeltmesinin aynı kaynak
`PYTHONPATH` koşulunda düzeltme sonrası **32 test / 14.783 s / OK** geçti.
Sekiz ölü hook kaynağı kaldırıldıktan sonra wheel, modern integrations,
packaged commands, migration preview/apply modülleri **72 test / 84.730 s /
OK** geçti. Resource allowlist tekrar kontrolünde eksik/stale kayıt yok.

Bu audit fiziksel Linux/macOS/WSL, kullanıcı oturumlu sağlayıcı veya yeni native
release build'i çalıştırmadı. Bu hostların başarısı bu belgeyle varsayılmaz.

## Native doğrulamanın bulduğu ek düzeltmeler — 2026-10-05

scope: project; confidence: verified; supersedes: []

- macOS console bootloader .app/Contents/MacOS konumunda kütüphaneleri
  Contents/Frameworks altında arıyor; bundle üreticisi bu yerleşime düzeltildi.
  Gerçek macOS frozen version/registry/maps/search/hook/MCP kapısı geçti.
- OS temp alias yolları ile canonical Roots/servis yolları fixture eşitliklerini
  ve fault injection hedeflerini bozuyordu. Gerçek junction ile tüm source
  testleri tarandı; yalnız yeni sahip olunan temp allocation ve fresh fixture
  kökleri resolve edilir. Kullanıcı/payload link veya reparse reddi gevşetilmedi.
- Windows geçici sharing/access replacement hatası modeli yeniden çağırabiliyordu.
  Hazırlanmış byte çıktı yalnız hata 5/32 için en fazla beş kez yayımlanmaya
  çalışılır; denemeler arasında Dashboard değişmişse durur. Kullanıcı değişikliği,
  kalıcı hata ve tek model çağrısı regresyonları geçti; özgün eşzamanlı test
  Python 3.13 üzerinde 100/100 geçti.
- GitHub step hata bildirimi sınırı bütün başarısız testleri göstermiyordu.
  Yalnız doğrulanmış public kimlikler tek annotation içinde toplanır; ham
  exception, subtest değerleri veya yerel yollar annotation'a aktarılmaz.

Güncel ürünle Windows gerçek native kabul 3/3 (321.464s), yerel tam Python suite
670 test (460.647s, 15 host skip) geçti. Yeni diagnostic testi ayrı doğrulandı.
Fiziksel Linux native/full-suite/smoke ve extracted makeself paketi CI'da geçti;
son fixture düzeltmeleriyle tüm platform kapılarının sonucu devam planında
kaydedilecektir. Yukarıdaki dört işlev/güvenlik sınırı bu düzeltmelerle kapatılmış
sayılmaz. Kullanıcının canlı kurulumu ve notları değiştirilmedi.

### Python sürüm uyumluluğu — 2026-10-05

37236806337 koşusunda üç native paket/kabul/smoke ve gerçek dağıtım biçimi
kapısı geçti; üç platformun Python 3.13 source kapısı da geçti. Python 3.10
source kapıları ise ResourceCatalog'ın yalnız 3.11+ üzerinde bulunan
`importlib.resources.abc` importu nedeniyle düştü. İzole gerçek CPython 3.10.22
aynı kök nedeni yeniden üretti. Python 3.10 `importlib.abc.Traversable`
uyumluluk yolu, mevcut runtime tür sembolünü ve introspection'ı koruyarak
eklendi. Dört mevcut kaynak/wheel izolasyon testi gerçek 3.10 üzerinde geçti.

Eski unittest çıktı biçiminin gizlediği public test kimlikleri de güvenli
biçimde normalize edilir; exception/subtest gövdeleri annotation'a alınmaz.
Bağımsız dar incelemede yeni önemli bulgu yok. Son ürün değişikliğinin tam
3.10 dizisi ve yeni platform koşusu devam planında kaydedilecektir.

Codex notify WSL yol dönüşümünde 3.12+ f-string söz dizimi de gerçek 3.10'da
SyntaxError verdi. Aynı hesap ayrı değişkene alınarak eski parser desteği
korundu; mevcut 10 turn-log/notify zincir testi hem 3.10 hem 3.12 üzerinde
geçti. 3.10 parser taraması 155 kaynak/test/araç Python dosyasının tamamında
başarılı. Değişiklik argv veya JSON payload semantiğini değiştirmez.

Son gerçek CPython 3.10.22 source koşusu **669 test, sıfır failure/error,
15 mevcut host skip** ile geçti; yalnız geçici harness üç ağır native kurulum
testini hariç tutar. Native kapı yeni CI koşusunda ayrıca zorunludur. Son
Windows paket/kurucu rebuild ve frozen komutlar geçti; ana klasörde 1057
dosyalı dağıtım kopyası SHA256 eşleşmesiyle doğrulandı, önceki paket korundu.

### CI süre ve hata teşhis sınırı — 2026-10-05

37239730909 üç native host kapısını geçti. Windows tam dizisi 7,3 dakika,
önceki dizisi 9,4 dakika ve fiziksel smoke 4,7 dakika sürdü; normal tek kullanıcı
kurulum süresi bu toplam değildir. Altı source işinden POSIX 3.10 testleri,
global os.name mock'unun stdlib Path seçimine sızmasını ve macOS wheel izolasyon
testini ortaya çıkardı. OS taklidi modül adaptörüyle sınırlandırıldı; wheel
adımının hata teşhisi yalnız sabit stage etiketlerini dışarı verir.

Kullanıcının bekleme/kota geri bildirimiyle erken üç-host 3.10 kapısı eklendi;
native aşamadaki üç mükerrer 3.13 tam dizisi kaldırıldı. Altı source işi her
hostta 3.10/3.13 tam dizisini native artifact ile çalıştırmaya devam eder.
Gerçek native/smoke/kurucu/launcher/zamanlayıcı/dağıtım biçimi ve shell kapıları
korunur. Yerel 3.10 erken 37 ve 3.12 değişen 19 vaka geçti; macOS wheel alt
adımının nedeni hâlâ doğrulanmalıdır. Yeni ürün davranışı veya test atlaması yok.

### Dar bağımlılık düzeltmesinin bağımsız incelemesi — 2026-10-05

Antigravity'nin dev extras içine setuptools>=69 eklemesi mevcut build-system
gereksinimini geliştirici ortamında da karşılıyor. İzole CPython 3.10 ortamında
65.5.1 backend ile wheel --no-isolation işlemi gereksinim hatası verdi;
aynı ortamda .[dev] kurulumu backend'i 84.0.0'a yükseltti. İlgili 38 test
7,785 saniyede geçti (bir mevcut host skip). Atlas 271 dosya kapsamını
doğruladı; 11 atlas testi 1,705 saniyede geçti. Yeni engelleyici bulgu yok.
Harici AI'nın 674 testlik tam koşu beyanı bu incelemenin bağımsız tam koşu
kanıtı olarak kullanılmaz; son platform sonucu kullanıcı çağrısında incelenir.

Yerel ortam bulgusu: global Python 3.13 paket metadata'sı editable kurulumun
installer-atlas çalışma ağacını gösterdiğini doğruladı. Bu inceleme global
kurulumu değiştirmedi. Çalışma ağacını arşivlemeden önce bu bağlantı ele
alınmalı; aksi halde global geliştirme komutu silinen kaynak yolunu gösterebilir.
