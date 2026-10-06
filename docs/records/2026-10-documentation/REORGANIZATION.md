# 📚 Belge Düzenleme Kaydı — 2026-10-05

scope: project; confidence: verified; supersedes: ["Belge incelemesini yalnız öneri aşamasında bırakma", "Aktif durumun tarihli yürütme planında tutulması"]

## 1. Kullanıcı kararı

Proje ve yerel çalışma klasörlerinin kullanılan süreç aracının adını taşımaması; eski README anlatımının örnek alınması; modüler, eksiksiz ve mevcut davranışı dürüstçe açıklayan bir belge merkezi hazırlanması istendi. Dosya atlasının korunması açıkça belirtildi.

## 2. Belge sorumlulukları

| Alan | Sorumluluk |
| --- | --- |
| `docs/README.md` | Okuma rotası ve bütün belge gruplarının giriş noktası |
| `docs/guides/` | Kurulum, günlük kullanım, ayar, sağlayıcı, bakım, yedek ve sorun giderme |
| `docs/ARCHITECTURE.md`, `SPECIFICATION.md` | Mevcut modüller, üç kök ayrımı ve davranış sözleşmeleri |
| `docs/PROJECT_STATUS.md` | Aktif durum ve kalan işlerin tek kaynağı |
| `docs/decisions/` | Kabul edilen tasarım ve işlem sözleşmesi kayıtları |
| `docs/development/` | Kaynak geliştirme, doğrulama ve CLI seçenek kataloğu |
| `docs/records/` | Tarihli planlar, denetimler ve doğrulamalar |
| `docs/REPOSITORY_MAP.md`, `repository_inventory.json` | Otomatik üretilen eksiksiz dosya atlası ve incelenmiş açıklamaları |

## 3. Taşınan ve korunan içerik

- İki tasarım belgesi `decisions/` altına alındı.
- Temel uygulama planı ve üç modül planı `records/2026-10-modular-foundation/` altında toplandı; temel doğrulaması aynı gruba alındı.
- Kaynak temizliği planı ve doğrulaması `records/2026-10-source-cleanup/` altında toplandı.
- Kurucu/atlas yürütme planı ve o dönemin denetimi `records/2026-10-installer-release/` altına alındı.
- Eski README, rehberler, mimari ve specification ile eski test matrisi `records/2026-09-legacy/` altında toplandı. Büyük README/SETUP parçaları birleştirilerek budanmadı.
- Önceki belge incelemesi ve dosya eki bu tarihli kayıt grubuna alındı.
- Toplam 27 mevcut belge yeni konumuna uyarlandı. Tarihsel içerik banner ile işaretlendi; ham metinler ayrıca yedeklendi.
- Güncel README ve rehberler kodla karşılaştırılarak yeniden yazıldı. Yeni ayar, günlük kullanım, yedek, sorun giderme, CLI ve geliştirici rehberleri eklendi.

## 4. Yerel kanıtların korunması

Yerel test ortamları, loglar ve yedekler Markdown değildir. Bunlar Git'e girmeyen `.local/archives/development-evidence-2026-10-05.zip` içinde korundu. ZIP içindeki yollar yalnız kayıt gruplarını taşır; kaldırılan kök klasör adı yeni bir klasör olarak üretilmedi.

| Ölçüm | Değer |
| --- | --- |
| Dosya sayısı | 18.317 |
| Kaynak byte toplamı | 492.846.803 |
| ZIP boyutu | 262.786.765 byte |
| ZIP SHA256 | `4b4ad2b68fe3e37635773560233b79669dbac2ca1acf9acb255d006bac1cff77` |

Her ZIP kaydının byte boyutu ve SHA256 değeri kaynakla karşılaştırıldı. Yanındaki JSON manifest dosya bazında bu değerleri tutar. `documentation-before-2026-10-05.zip` düzenleme öncesi belge metinlerini korur. Arşivlenmiş sanal ortamlar tarihsel kanıttır; taşınmış executable/absolute path içerebilir ve aktif geliştirme ortamı sayılmaz.

## 5. Dürüstlük düzeltmeleri

- SQLite FTS5/BM25 araması embedding/anlamsal arama olarak sunulmuyor.
- Yerel kasa, model çağrılarının çevrimdışı veya ücretsiz olduğu anlamına gelmiyor.
- Genel `auto` model kullanımında auth/config hatasından sonra başka sağlayıcı denenebilir; bütün dallarda daima durduğu iddiası kaldırıldı.
- Provider izin flag'leri genel bir işletim sistemi sandbox garantisi olarak sunulmuyor.
- Yerel gateway loopback'e bağlanır; permissive CORS ve auth/CSRF sınırları açıklandı.
- Windows silent kurucusu `/VAULT` ve `/DATA` kullanır. Pending sonucu son makbuz doğrulaması gerektirir; OperationResult içinde ayrıca receipt alanı yoktur.
- Geçmişteki CI başarısı yeni belge düzenlemesinin CI sonucu veya public native release olarak gösterilmiyor.

Bu çalışma canlı program veya kişisel not kasası kurulumu yapmaz. Hafıza protokolü kapsamında eski belge bağlantıları, devir notları ve adlandırma kuralı güncellendi; eski hafıza metinleri ayrı yerel ZIP'te korundu. Ürün modüllerinin davranışı bu belge düzenlemesiyle değiştirilmez.

## 6. Belge adresleri

Önceki konumlar süreç aracı adına yer vermeden belge türüyle belirtilmiştir. Ham tam yollar başlangıç ZIP yedeğinde korunur; aşağıdaki yeni yollar gerçek repo dosyalarıdır.

| Önceki belge / grup | Yeni konum |
| --- | --- |
| Tasarım: `2026-10-03-modular-foundation-design.md` | [docs/decisions/MODULAR_FOUNDATION.md](../../decisions/MODULAR_FOUNDATION.md) |
| Tasarım: `2026-10-03-modular-foundation-operations.md` | [docs/decisions/OPERATIONS.md](../../decisions/OPERATIONS.md) |
| Uygulama planı: `2026-10-03-modular-foundation.md` | [docs/records/2026-10-modular-foundation/IMPLEMENTATION.md](../2026-10-modular-foundation/IMPLEMENTATION.md) |
| Uygulama planı: `2026-10-03-modular-foundation-core.md` | `IMPLEMENTATION.md` içinde birleştirildi; yerel arşivde |
| Uygulama planı: `2026-10-03-modular-foundation-services.md` | `IMPLEMENTATION.md` içinde birleştirildi; yerel arşivde |
| Uygulama planı: `2026-10-03-modular-foundation-delivery.md` | `IMPLEMENTATION.md` içinde birleştirildi; yerel arşivde |
| Uygulama planı: `2026-10-04-source-cleanup.md` | `VERIFICATION.md` içinde birleştirildi; yerel arşivde |
| Uygulama planı: `2026-10-04-installer-atlas-release.md` | [docs/records/2026-10-installer-release/EXECUTION.md](../2026-10-installer-release/EXECUTION.md) |
| Doğrulama: `2026-10-04-modular-foundation.md` | [docs/records/2026-10-modular-foundation/VERIFICATION.md](../2026-10-modular-foundation/VERIFICATION.md) |
| Doğrulama: `2026-10-04-source-cleanup.md` | [docs/records/2026-10-source-cleanup/VERIFICATION.md](../2026-10-source-cleanup/VERIFICATION.md) |
| Denetim / inceleme: `REPOSITORY_AUDIT.md` | [docs/records/2026-10-installer-release/REPOSITORY_AUDIT.md](../2026-10-installer-release/REPOSITORY_AUDIT.md) |
| Denetim / inceleme: `TEST-MATRIX.md` | `records/2026-09-legacy/TEST-MATRIX.md` (yerel arşivde) |
| Denetim / inceleme: `DOCUMENTATION_REVIEW.md` | `records/2026-10-documentation/REVIEW.md` (yerel arşivde) |
| Denetim / inceleme: `DOCUMENTATION_REVIEW_FILES.md` | `records/2026-10-documentation/REVIEW_FILES.md` (yerel arşivde) |
| Eski ürün: `ARCHITECTURE.md` | `records/2026-09-legacy/ARCHITECTURE.md` (yerel arşivde) |
| Eski ürün: `README-part-01.md` | `records/2026-09-legacy/README-part-01.md` (yerel arşivde) |
| Eski ürün: `README-part-02.md` | `records/2026-09-legacy/README-part-02.md` (yerel arşivde) |
| Eski ürün: `README.md` | `records/2026-09-legacy/README.md` (yerel arşivde) |
| Eski ürün: `SPECIFICATION.md` | `records/2026-09-legacy/SPECIFICATION.md` (yerel arşivde) |
| Eski ürün: `BOOTSTRAP.md` | `records/2026-09-legacy/guides/BOOTSTRAP.md` (yerel arşivde) |
| Eski ürün: `MULTI_AI.md` | `records/2026-09-legacy/guides/MULTI_AI.md` (yerel arşivde) |
| Eski ürün: `SETUP-part-01.md` | `records/2026-09-legacy/guides/SETUP-part-01.md` (yerel arşivde) |
| Eski ürün: `SETUP-part-02.md` | `records/2026-09-legacy/guides/SETUP-part-02.md` (yerel arşivde) |
| Eski ürün: `SETUP-WINDOWS.md` | `records/2026-09-legacy/guides/SETUP-WINDOWS.md` (yerel arşivde) |
| Eski ürün: `SETUP.md` | `records/2026-09-legacy/guides/SETUP.md` (yerel arşivde) |
| Eski ürün: `UNINSTALL.md` | `records/2026-09-legacy/guides/UNINSTALL.md` (yerel arşivde) |
| Eski ürün: `UPDATE.md` | `records/2026-09-legacy/guides/UPDATE.md` (yerel arşivde) |

## 7. Bu değişikliğin doğrulaması

| Kontrol | Sonuç / kapsam |
| --- | --- |
| Atlas regresyonu | `python -m unittest tests.repository_map_test -v`: 11 test geçti |
| Mevcut public belge sözleşmeleri | `tests.multiai_test` içindeki 3 public-doc testi geçti |
| CLI örnekleri | Güncel rehberlerdeki 39 örnek parser ile kontrol edildi; komutlar uygulanmadı |
| Dosya atlası | 287 kaynak dosyası; eksik/fazla/eski hash/üretim farkı kontrolü geçti |
| Yerel dosya bağlantıları | 52 Markdown belge tarandı; 576 dosya bağlantısı kontrolünde kırık yol yok |
| Belge boyutu | Atlas hariç Markdown belgeleri 25 KB bölme barajının altında |
| Kaynak davranışı | `src/`, `packaging/`, `tests/`, `pyproject.toml` HEAD farkı yok; yalnız atlas aracının yerel kanıt dışlama adı değişti |
| Eski klasörler | Önceki süreç adlı yerel/koordinasyon dizinleri ve eski docs history kökü kaldırıldı |
| Build çıktıları | build/dist yok; bu belge işi native paket üretmedi |
| Yerel arşiv | ZIP giriş byte/hash kontrolü ve silmeden önce 18.317 kaynak dosyasının yeniden hash kontrolü geçti |
| Yayın | Bu değişiklik yerel çalışma ağacında; bu oturum commit/push veya yeni CI koşusu yapmadı |

Bunlar mevcut native ürünün yeniden bütün platformlarda sınandığı anlamına gelmez. Önceki ürün CI sonucu kendi commit/tarihiyle test matrisinde korunur. Atlas sayısı bu değişikliğin kaynak envanteridir; yerel üçüncü taraf bağımlılık dosyalarını içermez.

## 8. İkinci aşama: Belge sadeleştirmesi — 2026-10-05

Kullanıcı yönlendirmesiyle belgeler sadeleştirildi, ara aşama taslakları ve yinelenen metinler temizlendi:

- **Eski ürün belgeleri (14 dosya):** `docs/records/2026-09-legacy/` altındaki 14 dosya kaldırıldı; ham metinler `.local/archives/` altındaki ZIP arşivlerinde korunmaktadır.
- **Birleştirilen görev planları (3 dosya):** `CORE.md`, `SERVICES.md` ve `DELIVERY.md` görev sözleşmeleri `IMPLEMENTATION.md` içinde özetlendi ve üç alt dosya kaldırıldı.
- **Birleştirilen kaynak temizliği planı (1 dosya):** `docs/records/2026-10-source-cleanup/EXECUTION.md` yürütme hedefleri aynı gruptaki `VERIFICATION.md` içine tarihli ek olarak aktarıldı ve kaldırıldı.
- **Kaldırılan inceleme taslakları (2 dosya):** `REVIEW.md` ve `REVIEW_FILES.md` kaldırıldı.
- **Kök denetim girişi:** `docs/REPOSITORY_AUDIT.md` kaldırıldı; güvenlik sınırları `SECURITY.md` içine, tarihli denetim `records/2026-10-installer-release/REPOSITORY_AUDIT.md` içine yönlendirildi.
- **Davranış düzeltmeleri:** `ARCHITECTURE.md` ve `DAILY_USE.md` içindeki derleme ve brifing filtreleri kod gerçeğine uygun düzeltildi (`compile_catch_up` dünü süzerken, `compile_memory` ve normal CLI `--before-date` verilmezse günün günlüğünü de işleyebilir; brifing exit 1 olsa bile dosya yazabilir).
- **Geliştirici ortamı:** `development/README.md` venv komutları Windows ve POSIX çalıştırıcılarıyla açıkça ayrıldı.
- **Kişisel tercihler:** Kullanıcının devreye alma tercihi Git dışındaki `.local/ROLLOUT.md` dosyasına alındı.

### Bağımsız inceleme — 2026-10-05

Silinen 21 dosyanın ham metinleri görev başlangıcı ZIP'iyle karşılaştırıldı;
onaylı tasarım ve tarihli test kanıtları korundu. Görev planlarının adım/örnekleri
yerel arşivdedir; IMPLEMENTATION bunların sözleşme özetidir. Canlı kurulumu da
tamamlanmış gibi gösteren “14 görev tamamlandı” ifadesi düzeltildi.

Ürün durumu, onaylı mimari ve kişisel rollout için eski yönlendirmeler ayrıldı;
PROJECT_STATUS kişisel tercihin içeriğini tekrar etmek yerine yerel kayda yönelir.
`briefing` komutunun `--before-date` kabul etmediği ve derleme hatası sonrasında
yazılmış brifing dosyasının sonraki çağrıyı atlatabileceği açıklandı. Geliştirici
rehberinin build/test/atlas komutları da venv çalıştırıcısına bağlandı.

Bu inceleme ürünün yeniden native doğrulaması değildir; kaynak kod ve canlı
kurulum değişmedi. Dar test, atlas, bağlantı ve parser sonuçları yerel devir
raporunda ayrı kaydedilir.
