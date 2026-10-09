# 📋 F7 Transcript Integrity Remediation Record — 2026-10-08

scope: project; confidence: verified; supersedes: ["İlk F7 uygulama kaydındaki tüm bulgular kapandı iddiası"]

## 1. Kapsam

Bu kayıt, F7 transcript güvenliği ve veri bütünlüğü düzeltmelerini belgeler.
İlk uygulamanın kapanış iddiası ikinci bağımsız incelemede reddedildi;
incelemede yeniden üretilen açıkların takip düzeltmesi bölüm 7'dedir.
İnceleme, doğrudan CLI/hook/API girişleri, catch-up akışı, provider kimliği,
kasa provenance’ı, kalıcı sahiplik durumu ve immutable transcript snapshot’ını
kapsar. Canlı kullanıcı kasası değiştirilmedi; tüm davranış kanıtları izole
geçici fixture’larla üretildi.

## 2. Kaynak korumaları (takip düzeltmesi dahil)

| # | Bulgu | Kapanış |
| --- | --- | --- |
| 1 | Lock timeout veya failure handler sahipliği korumasız değiştiriyor | Ret/timeout yalnız health tanısı yazar; kabul edilmiş model hataları session kilidi altında kendi failure checkpoint'ini günceller, pending özet korunur |
| 2 | Direct flush veya precompact provenance'ı atlıyor | CLI hook girdisi ortak doğrulamaya taşınır; precompact arşivi aynı kilit/doğrulama yolunda immutable byte yazar ve yeni sahipliği arşivden önce kaydeder |
| 3 | Compatibility-only legacy takeover | `last-flush.json` tek başına sahiplik vermez; eksik per-session kimlik/provider/status/zaman veya orphan daily block reddedilir |
| 4 | Çelişen native ID'ler | Session metadata ve normal kayıtlardaki native session alanları birlikte doğrulanır; sıradan message `id` alanı session ID sayılmaz; UUID kimliği kanonikleştirilir |
| 5 | Malformed metadata absent sayılıyor | Nested metadata/workspace container'ları, explicit null ve hook/provider alanları strict doğrulanır; normalizasyon available çelişkileri gizleyemez |
| 6 | Snapshot TOCTOU | Provenance, model girdisi, precompact arşivi ve catch-up timestamp aynı immutable snapshot'tan okunur |
| 7 | Provenance yarışı ve çelişki kaybı | DataRoot provenance kilidi yazmaları serileştirir; lifecycle cleanup provenance kaydını otomatik silmez |

## 3. Merkezi korumalar

- `TranscriptSnapshot`: path ile içeriği tek immutable snapshot’a bağlar.
- `_session_id_values` ve `_workspace_values`: provider-native kimlik ve nested
  metadata alanlarını strict tip kurallarıyla çıkarır.
- `_provenance_lease`: hook provenance yazmalarını DataRoot düzeyinde kilitler.
- `_owned_session_state`: per-session kimlik, provider, yol ve checkpoint alanlarını
  doğrular; compatibility-only sahipliği reddeder.
- `_flush_session_transcript`: direct CLI/hook/API, precompact arşivi ve catch-up için
  ortak güvenlik sınırıdır.
- `_record_flush_failure`: yalnız doğrulanmış ve kilit içindeki oturumun failure
  checkpoint'ini günceller; pending checkpoint'i korur. Dış ret handler'ları health yazar.

## 4. İlk uygulama doğrulaması (tarihsel bildirim)

Aşağıdaki sonuçlar önceki uygulama oturumunun bildirimidir; takip düzeltmesinin
taze kanıtı veya bağımsız kabulü değildir.

| Kapı | Sonuç |
| --- | --- |
| `python -m unittest tests.f7_transcript_integrity_test -v` | 24/24 PASS |
| `python -m unittest tests.f7_transcript_integrity_test tests.scripts_test tests.turn_log_pipeline_test -v` | 97/97 PASS, 2 environment skip |
| `python tests/run_all.py --python-only` | 948/948 PASS, 16 skip, 798.23 s |
| `python tools/verify_distribution.py --distribution dist/RespectedBrain --platform windows` | PASS |
| `python tests/smoke/platform_smoke.py --fixture-provenance` | 23/23 VERIFIED |
| `powershell -NoProfile -ExecutionPolicy Bypass -File tests/install_windows_test.ps1` | 4/4 PASS |
| `powershell -NoProfile -ExecutionPolicy Bypass -File tests/windows_launchers_test.ps1` | 7/7 PASS |
| `powershell -NoProfile -ExecutionPolicy Bypass -File tests/briefing_schedule_windows_test.ps1` | 15/15 PASS |
| `bash tests/hooks_test.sh` | 8/8 PASS |
| `bash tests/upstream_sync_test.sh` | 9/9 PASS |
| `python tools/repository_map.py --check` | 291 files, check passed |

## 5. Dış sınırlar

- İlk oturumda vulnerable baseline üzerinde kırmızı test tekrarı koşulmadı.
  Takip düzeltmesinde yeni kalıcı testler kaynak değişmeden önce hataları yakaladı;
  ilk 35 testlik kırmızı koşuda 17 assertion başarısız oldu.
- Commit/push yapılmadığı için yeni bir GitHub Actions CI koşusu tetiklenmedi.
  Önceki CI sonucu bu değişikliklerin kanıtı değildir.
- Canlı provider token/oturumu ve sağlayıcı OS sandbox davranışı doğrulanmadı.
- Gerçek GitHub Actions OIDC/Sigstore attestation/signature ve Authenticode
  imzalı outer installer doğrulanmadı.
- Doğrulama bu hostta Windows native ortamında yapıldı; saf Linux, macOS ve WSL
  davranışı bu kayıtla doğrulanmış sayılmaz.

## 6. Kabul durumu

Kaynak düzeltmeleri ve regresyonları bu kayıtta izlenir. Güncel kabul/ürün durumu
yalnız [PROJECT_STATUS](../../PROJECT_STATUS.md) içindedir; tarihsel test sonuçları
yeni frozen paket veya bağımsız kabul kanıtı değildir.

## 7. İkinci bağımsız inceleme sonrası takip düzeltmesi — 2026-10-08

İnceleme, precompact arşiv bypass'ını, CLI hook provenance kaybını, normal
kayıtlardaki native ID/workspace atlamasını, nested malformed/explicit null
kabulünü, compatibility-only devralmayı ve yedi günlük provenance temizliğiyle
çelişkinin unutulmasını yeniden üretti. Ayrıca provider değiştirme, UUID harf
büyüklüğüyle duplicate üretme ve snapshot dışındaki timestamp okuması saptandı.

Takip uygulaması bu akışları ortak kilit/doğrulama sınırına bağlar. Precompact
arşivinde `archived` checkpoint yeni oturumun yol/provider sahipliğini tutar;
aynı kaynaktan normal flush devam eder, başka kaynak devralamaz. Eksik eski
sahiplik kayıtları otomatik taşınmaz veya yeniden sahiplenilmez. Hook workspace
gerçekten yoksa yok olarak kalır; yanlış tür veya çelişkili alanlar reddedilir.
Bozuk hook girdisine ret verilirken provider'ın native yanıt protokolü korunur.

Kalıcı testler `tests/f7_transcript_integrity_test.py` içinde genişletildi.
Eski compatibility-only pozitif test, byte koruyan ret testine çevrildi.
Gerçek lock timeout testi artık status, owner transferi ve compatibility byte'ını
da doğrular. Gerçek Windows subprocess fixture'ı aynı session ID'yi provider'lar
arasında değiştirmek yerine aynı provider kimliğini korur.

Taze son regresyon koşusu: 308 test, 306 PASS ve 2 ortam skip (54.818 s).
Bu koşu F7, scripts, turn-log, foundation-memory, multi-AI, MCP/features,
entry-review, Windows-native, output-normalization, foundation-integrations,
foundation-services, boundary-regression ve adversarial-quality modüllerini kapsar.
F7 modülünün 42 testi (18 yeni test dahil), native hata yanıtı ve nested hook
provider çelişkisi bu son koşuda geçti. Önceki paket, tam suite ve CI sonuçları
yeni kaynak değişikliğine taşınmaz.

Hızlı kaynak düzeltmesi kapsamında frozen EXE/Setup yeniden üretilmedi, tam ürün
suite'i tekrar koşulmadı, commit/push ve canlı rollout yapılmadı.

## 8. 42 kalıcı regresyonun bağımsız incelemesinden sonraki üç düzeltme — 2026-10-08

Salt okunur incelemede mevcut 42 F7 regresyonu ve bağlantılı 308 testlik koşu
geçti; ek izole denemeler üç ayrı hatayı yeniden üretti. Kaynak değişmeden önce
beş yeni kalıcı test eklendi: 47 testlik kırmızı koşuda 13 assertion başarısız
oldu. Böylece yeşil eski regresyonlar bu üç hatanın kapanış kanıtı sayılmadı.

| Yeniden üretilen hata | Kaynak düzeltmesi ve kalıcı davranış kontrolü |
| --- | --- |
| Antigravity'nin değişken `conversationId`/`conversation_id` invocation kimliği kalıcı transcript kimliğiyle çelişki sayılıyor | Adaptör bu iki native invocation alias'ını ortak session doğrulamasından ayırır. Birbirleriyle çelişen invocation alias'ları ve kalan açık/nested kalıcı kimlikler reddedilir; ret native yanıt protokolünü korur. Gerçek bridge → lifecycle → CLI → flush akışı iki farklı invocation için aynı owner ve tek günlük bloğunu doğrular. |
| `fail` checkpoint'indeki bozuk `attempts` bütün catch-up taramasını kesiyor | Failed sayaç yalnız negatif olmayan gerçek `int` olabilir; eksik eski sayaç için mevcut varsayılan korunur. Bozuk aday `session-state-invalid` olarak raporlanır, byte'ları korunur ve sağlıklı aday işlenir. String, null, bool, negatif, kesirli sayı, list ve object regresyonları vardır. |
| Şemaya uyan model çıktısındaki yönetilen session işaretçisi günlük bloğunu bozuyor | Özet doğrulaması ve doğrudan günlük yazıcısı `<!-- RESPECTED-SESSION:` prefix'ini yazmadan önce reddeder. Kendi BEGIN/END veya başka oturum işaretçisi insan günlüğünü değiştiremez; temiz çıktı ile sonraki retry tek geçerli bloğu günceller. |

Kaynak düzeltmesinden sonraki ilk odaklı koşu:
`python -B -m unittest tests.f7_transcript_integrity_test tests.multiai_test tests.turn_log_pipeline_test`
ile 106/106 PASS (14.818 s). F7 modülü 47 kalıcı test içerir.

Taze tam Python suite koşusu:
`python -B -m unittest discover -s tests -p '*test*.py' -v`
ile 971 test / 955 PASS / 16 platform-ortam skip / sıfır hata (947.233 s,
exit 0). Bu keşif, `tests/run_all.py` içindeki Python test kapısının bütün
modüllerini çalıştırır. F7 regresyonları, gerçek Inno kurulum/update/uninstall,
kullanımdaki EXE update/health rollback ve readonly AppRoot kontrolleri dahildir.
Native fixture testleri diskteki mevcut `dist/RespectedBrain` paketini kullanır;
sonuç, yeni F7 kaynak değişikliğinin frozen EXE'ye taşındığı anlamına gelmez.
PowerShell/Bash suite kapıları bu oturumda yeniden koşulmadı.

Yerel ham suite logu Git dışındaki
`.local/archives/f7-20261008-invocation-counter-markers-suite.log` dosyasındadır.

Bu oturum canlı kasayı/programı değiştirmez, eski bozuk checkpoint veya insan
günlüğünü otomatik onarmaz. Frozen EXE/Setup üretimi, canlı provider ve dış
imza/attestation kabulü bu kaynak düzeltmesinin kanıt kapsamına dahil değildir.

## 9. Ortak kayıt sözleşmesi ve kaldırma kapanış kapsamı — 2026-10-08

scope: project; confidence: verified; supersedes: ["47 F7 regresyonunun bütün pending checkpoint alanlarını doğruladığı çıkarımı"]

Sonraki izole kontrol, pending içindeki string `daily_written="false"` ile günlük yazılmadan başarı ve `provider="claude"` ile Codex owner değişimi üretti. Kapanış kapsamı yalnız bu iki değere değil, kaydın bütün tüketilen alanlarına genişletildi. Top-level finite timestamp, negatif olmayan gerçek int turns/attempts ve sha256 hash; pending summary, timezone içeren ISO zaman, desteklenen reason, owner ile aynı provider ve gerçek bool daily_written birlikte doğrulanır. Eksik/bozuk pending kaydı yeniden model üretip üzerine yazılmaz; checkpoint baytları korunur, giriş başarısız döner. Naive API zamanı yeni checkpoint yazılmadan yerel timezone ile normalize edilir; önceki retry davranışı korunur.

`daily_written=True` tek ve doğru sıralı BEGIN/END bloğunun asıl günün günlük dosyasında bulunmasını gerektirir. Eksik günlük, insanın marker'sız değiştirdiği dosya, çift blok ve bozuk marker başarı sayılmaz. Marker içindeki insan editleri yeniden yazılmaz. Bozuk health JSON içindeki NaN/Infinity hata raporlamasını çökertmez; geçersiz payload güvenli biçimde bırakılıp yeni tanı yazılır.

Kaynak kaldırma incelemesindeki iki bulgu da aynı görev kapsamındadır: normal/keep-data/uyumluluk purge tercihi deferred helper ve doğrudan servis için aynı değeri taşır. Yeni kasanın beş yerel hook dosyası ExternalChange olarak transaction günlüğü ve uninstall manifestine kaydedilir. Yerel kayıtlar global entegrasyon bayrağı kapalıyken update/repair boyunca sahipli kalır; uninstall değişmemiş bağlantıları kaldırır, insan editini conflict ile korur. Health hatasında kayıtlar geri alınır.

| Kabul davranışı | Kanıt kapsamı |
| --- | --- |
| Native/workspace/session/provider sahibi; direct, raw hook, catch-up ve precompact | Önceki 47 regresyon ile ortak owner tüketim sınırı |
| Her pending alanının eksikliği, yanlış türü veya tutarsız değeri | Tablo alt senaryoları; sıfır model çağrısı, checkpoint/compatibility bayt koruması |
| Top-level state türleri ve NaN/Infinity | Ret ve sağlık raporlaması regresyonları |
| Bozuk aday yanında sağlıklı catch-up | Sağlıklı aday tek model çağrısıyla işlenir; bozuk pending korunur ve report result başarısızdır |
| Günlük/Companion başarısızlığından sonra retry, kısa precompact ve insan editleri | foundation_memory ve turn_log_pipeline gerçek dosya/event kontrolleri |
| Uninstall tercihinin ertelenen ve doğrudan yolda eşitliği | Üç flag girişi × iki dispatch yolu |
| Yerel hook lifecycle ve not koruması | Gerçek NativeBackend geçici köklerinde setup → update → repair → uninstall; purge/keep-data, changed-hook conflict ve rollback |

Yeni testler kaynak düzeltmesinden önce RED koşuldu. İlk üç modüllük 70 test koşusunda 62 başarısız alt senaryo ve iki fixture alan-adı hatası görüldü; fixture düzeltmesinden sonraki ayrı yerel hook RED koşusu iki gerçek sahiplik assertion'ında başarısız oldu. İlk kaynak düzeltmesinden sonra naive zamanla retry kullanan üç mevcut assertion timezone eksikliğini gösterdi; API zaman normalizasyonuyla 115 odaklı test geçti (34.928 s). Ayrı health NaN RED önce başarısız, düzeltme sonrası 1/1 yeşildir. F7 modülü bu genişletmeden sonra 52 kalıcı test içerir.

Windows EXE/Setup güncel kaynakla yeniden üretildi; PyInstaller 6.22.3 / Python 3.13.15 ve Inno başarılı derleme verdi. Frozen PYZ'deki 84/84 ürün modülü kaynakla opcode, sabitler, nested code, closure, exception table ve stack size dahil eşittir. Yerel kanıtlar `.local/archives/f7-checkpoint-uninstall-*` altındadır; hash'ler `f7-checkpoint-uninstall-source-compare.json` içindedir.

Yeni frozen EXE'nin `welcome` komutu geçici AppRoot/DataRoot/VaultRoot ile kontrol edildi: eksik profil GUI açılışı timeout ile exit 0 (2.056 s, stderr boş), tamamlanmış profil aynı komutta GUI'yi atlayarak exit 0 (0.218 s) verdi. Her iki çağrıdan sonra fixture dosya hash'leri değişmedi. Bu kontrol GUI'de alan doldurma/kaydetme etkileşimini veya gerçek yayın provenance'ını doğrulamaz; profil tamamlandıktan sonra tekrar sormama davranışını ve gerçek frozen Tcl/Tk başlangıcını doğrular. Kanıt `f7-checkpoint-uninstall-gui-final.json` içindedir.

İlk genel `tests/run_all.py` koşusunun Python bölümü 980 testte 961 PASS / 16 skip / 2 error / 1 failure verdi (989.953 s). İki wizard fixture'ı yerel hook'u eski doğrudan dosya yazımıyla varsayıyordu; gerçek NativeBackend'e geçirilerek ExternalChange sonrası final UUID/stable launcher dosya baytları sınandı. DNS shutdown assertion'ı interpreter/import başlangıcını da 1.5 s sınırına dahil ediyordu; tek başına üç tekrar geçti. Test artık resolver'ın gerçekten bloklandığını readiness ile doğrular ve yalnız bundan sonraki proses çıkışını ölçer. Düzeltilmiş iki modül ile bütün bağlantılı odak kapsamı 139/139 PASS (58.936 s) verdi. Ürün kaynak kodu bu test uyarlamalarında değişmedi. Sonraki ortak işlem nedeni düzeltmesi ve son artifact kabulü aşağıdadır; ilk genel koşunun başarısız sonucu korunur.

## 10. Son kaynak ve artifact kabulü — 2026-10-09

Yazıcı ve okuyucu aynı `FLUSH_REASONS` kümesini kullanır. Desteklenmeyen reason girişleri model çağrısı veya checkpoint oluşturmadan reddedilir. Son regresyon RED aşamasında beş alt senaryoda başarısız oldu; düzeltmeden sonra F7 + multiai + turn pipeline 112/112 PASS (18.759 s). F7 modülü 53 kalıcı testtir.

Son kaynakla yeniden build başarılıdır. 84/84 frozen ürün modülünde semantik fark yoktur. Son artifact hash'leri:

| Dosya | SHA256 |
| --- | --- |
| `dist/RespectedBrain/respectedbrain.exe` | `0e03c02e6b5fe2fb7422df2122d8811a46a2e427b2f6b6a11ae7de72f7ad8109` |
| `dist/RespectedBrain/distribution.json` | `a014de5784740b515c5a663d4a789ab9d68e68e8c6a3e3467a18d5b6a97bb342` |
| `dist/RespectedBrain-Windows-Setup.exe` | `6629ec33dd6ca2ea2ba5f6274b42a5ff31cd92dc624d225a15f07db2f772d924` |

Kanıt `f7-checkpoint-uninstall-source-compare-final.json` içindedir. Aynı EXE ile GUI başlangıcı 2.009 s ve tamamlanmış profil atlaması 0.264 s, her ikisi exit 0/stderr boş/not hash'leri sabit verdi (`f7-checkpoint-uninstall-gui-current.json`). Alan doldurma/kaydetme etkileşimi bu smoke'un kapsamı değildir.

Yerel hook sahipliği kontrolüyle güçlendirilen fiziksel Windows smoke'un ilk koşusu 24/24 VERIFIED verdi (`f7-checkpoint-uninstall-native-smoke-final.json`). Son reason guard build'inden önceki fixture paketi kullandığı için bu sonuç son hash'e mal edilmez. Son hash ile tekrar edilen aynı smoke da 24/24 VERIFIED verdi (`f7-checkpoint-uninstall-native-smoke-current.json`): gerçek frozen kurulum/repair, iki update, deferred self-update receipt, yerel hook sahipliği ve kaldırılması, insan notları/state/kullanıcı dosyası koruması ve temp-home kayıtlarının geri alınması geçti. Kabul sonrası 84/84 semantik karşılaştırma ve üç artifact hash'i değişmedi (`f7-checkpoint-uninstall-source-compare-after-acceptance.json`). Provenance fixture-policy kullanır; gerçek yayın imzası değildir.

İlk genel koşunun Python dışındaki bütün kapıları geçti: native distribution 3.82 s, fiziksel smoke 432.04 s, PowerShell kurulum 837.99 s, launcher 11.91 s, zamanlayıcı 6.13 s, Bash hooks 0.71 s ve upstream sync 7.28 s. Genel exit 1 yukarıdaki tarihsel Python hataları nedeniyle korunur; bu log genel yeşil sonuç diye sunulmaz. PowerShell kurulum kapısı dört `foundation_native_install_test` vakasını gerçek Windows proseslerinde yeniden çalıştırmıştır.

Son Python keşfi, PowerShell kapısının ayrı çalıştırdığı bu dört uzun native vakayı tekrarlamadan kalan 977 vakayı çalıştırır (`f7_python_acceptance.py`). İlk koşusu 290.364 s içinde 959 PASS / 16 skip / 1 failure / 1 error verdi. İki hata F7 bridge → CLI fixture'ının sabit `2026-10-08.md` yolunu gerçek saatle karşılaştırmasıdır; gece yarısından sonra ürün doğru yeni günün günlüğünü yazarken fixture eski dosyayı aradı. Bu iki olumlu fixture'da CLI saati NOW ile sabitlendi; 53/53 F7 PASS (7.339 s). Ürün kaynağı/artifact hash'i değişmedi. Tarihsel hata logu `f7-checkpoint-uninstall-python-midnight-red.log` olarak korunur.

Temiz tekrar: **977 test / 961 PASS / 16 koşullu skip / 0 failure / 0 error**, 280.218 s, exit 0 (`f7-checkpoint-uninstall-python-final.log`). F7 53 vakası bu keşfin içindedir. Dört native vaka ayrı PowerShell kapısında geçtiği için 981 vakalık toplam keşfin kapsamı iki koşu üzerinden tamamlanmıştır; bütün `run_all.py` komutunun tek seferde yeşil çıktığı iddia edilmez. 16 skip'in platform/dış bağımlılık koşulları ve fixture provenance gerçek provider/imza kabulü yerine geçmez.

Gerçek yayın attestation/Authenticode ve canlı sağlayıcı/OS sandbox kabulü yerel build veya fixture provenance ile doğrulanmış sayılmaz. Bozuk geçmiş kullanıcı kaydı otomatik onarılmaz. Kişisel eksik kaldırma kalıntılarının envanteri, yedekli temizliği ve artık kurulu program olmadığı bilgisi Git dışındaki `.local/ROLLOUT.md` içindedir.
