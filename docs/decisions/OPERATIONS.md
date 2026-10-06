---
title: Respected Brain — Kurulum ve Geçiş Sözleşmeleri
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

> Tarihli karar/işlem kaydı. Eski durum ve komutlar bu tarihin bağlamındadır; güncel yapılacaklar değildir. Bağlantılar ve araç talimatları 2026-10-05 belge düzenine uyarlandı; ham başlangıç kopyası yerel documentation-before ZIP arşivindedir. Eski süreç/klasör adları nötr tanımlara çevrildi; bu tarihsel tanımlar bugünkü dosya yolu değildir. [Aktif durum](../PROJECT_STATUS.md).


# Kurulum ve Geçiş Sözleşmeleri

Bu belge [modüler temel tasarımının](MODULAR_FOUNDATION.md)
parçasıdır. Program/veri/kasa konumları ve modül sınırları ana sözleşmede
yaşar; burada komut, kurulum, veri koruma ve kabul koşulları tanımlanır.
Yazılı sözleşme 2026-10-03 tarihinde kullanıcı tarafından onaylandı; canlı
geçiş yapılmamıştır.

## 1. Tek CLI ve entegrasyon sözleşmesi

Ürün komutları aynı paket dağıtıcısını kullanır:

```text
respectedbrain setup --vault <path>
respectedbrain configure
respectedbrain vault register|list|discover
respectedbrain dashboard --vault-id <id>
respectedbrain hook --provider <name> --event <event> --vault-id <id>
respectedbrain mcp --vault-id <id>
respectedbrain briefing --vault-id <id>
respectedbrain compile --vault-id <id>
respectedbrain update --package <path>
respectedbrain repair --vault-id <id>
respectedbrain migrate --legacy-root <path> --vault <path> [--apply]
respectedbrain uninstall
```

Kasaya bağlı komutlar UUID yerine açık `--vault <path>` de kabul eder.
Hook'lar mevcut transcript/session argv ve stdin alanlarını provider
adaptörüyle korur. Event normalizasyonu oturumun idempotency anahtarını
değiştirip eski konuşmayı tekrar kaydetmez.

Global hook, MCP, zamanlayıcı ve kısayol mevcut `respectedbrain` başlatıcısını
çağırır. `.py` dosyasının kurulu konumunu, sistem Python'ını, `.beyin` veya
`runtime/scripts` yolunu sabitlemez. Native Windows `.exe`, POSIX kurulum
native CLI kullanır. WSL seçilmişse kayıt sırasında WSL içinde mevcut
başlatıcı doğrulanır ve Windows/WSL sınırındaki argv yolları dönüştürülür;
Linux Python'a Windows dosya yolu verilmez. WSL olmayan Windows kurulumda
WSL varsayılan bağımlılık olmaz.

Global/MCP/zamanlayıcı seçenekleri tek desired-state kaydından okunur.
Kapalı özellik migration, repair veya update tarafından açılmaz. Harici
ayar dosyalarında yalnız sahipli bölüm güncellenir, mevcut kullanıcı
ayarları korunur, önce yedek alınır. Her harici kayıt başlatıcı ve kasa
kimliğini içerir. Native hook/MCP protokol stdout'u logla kirletilmez.

Bir geçiş sürümü boyunca eski komut başlatıcıları gerekirse ince uyumluluk
sarmalayıcısı kalabilir. Ürün mantığı içermez; yeni CLI'a aktarır ve çıkış
kodunu korur. Yeni paket ikinci eski motor ağacı taşımaz.

## 2. Template ve kullanıcı özelleştirmesi

Yeni kasa oluşturma: paket resources/vault-template okunur, profil
yer tutucuları doldurulur, geçici stage doğrulanır ve hedefe aktarılır.
Hedef dolu ve kasa olarak kayıtlı değilse hiçbir dosya değiştirilmez.
Var olan kasa update işleminde template yeniden kopyalanmaz.

`📋 Templates` ve `.obsidian` kopyalandıktan sonra kullanıcı içeriğidir.
Kullanıcı düzenlemeleri program kaynaklarıyla senkronize edilmez.
Kullanıcının Companion/Core/Kurallar/Last-Session/Threads/Journal dosyaları
paket instructions dosyasından yeniden üretilmez.

Paket instructions/skills varsayılanları immutable kaynaklardır. Güncel
vault kimliği ve tercihleri global entegrasyon render sırasında bağlama
eklenir. Kullanıcının mevcut kişiselleştirilmiş motor instructions/skills
dosyaları varsa yalnız paketle birebir aynı olanlar varsayılan sayılır;
farklı olanlar DataRoot/vaults/<id>/overrides altında korunur ve render
önceliğinde paket varsayılanını geçer. overrides çalışma state'i değildir.

## 3. Kurulum, güncelleme, onarım ve kaldırma

### Yeni kurulum

Platform kabuğu tek AppRoot paketini stage edip doğrular. Ortak setup
hizmeti kasa yaratma/kayıt, kullanıcı config'i ve seçilmiş entegrasyonları
uygular. İşlem sonunda AppRoot, DataRoot, VaultRoot sözleşmesi doğrudan
oluşur. Önce `.beyin/scripts` içeren kasa yaratıp sonra temizleyen ara
kurulum modeli kaldırılır.

Windows yeni Inno paketinde AppId korunur; uygulama hedefi AppRoot'tur.
Eski kasa yolu installer'ın program hedefi olarak yeniden kullanılmaz
(`UsePreviousAppDir=no`). Kasa ayrı kullanıcı ayarıdır. Kaldırıcı AppRoot/
uninstall altında kayıtlıdır. Installer uygulama/veri konumunu karıştırmaz.

### Güncelleme

Yeni paket ayrı stage edilir, kaynaklar/importlar/CLI sağlığı doğrulanır.
Aktif yazıcılar durdurulur ve işlem kilidi alınır. Eski sahipli uygulama
dosyaları yedeklendikten sonra yeni paket etkinleştirilir. İnce launcherlara
bağlanan harici kayıtlar gerektiğinde aynı işlemle yenilenir. Sağlık veya
entegrasyon hatasında eski program ve değişmiş harici kayıtlar geri alınır.

Özel atomik dizin değişimi varsayılmaz: Windows'ta açık executable ve
Inno işlem yaşam döngüsü dikkate alınır; manifest/journal ile doğrulanabilir
stage, activation ve rollback uygulanır. Kasa notları bu işlemin payload'ı
değildir. Config şema dönüşümü varsa kendi yedeği ve rollback'i vardır.
Uygulama klasörü sürümlere göre çoğaltılmaz; kalıcı ikinci aktif motor yoktur.

### Onarım

Paketin sahipli kaynakları ve seçilmiş bağlantılar doğrulanır; kullanıcı
notları üzerine template yazılmaz. Cache gerektiğinde yeniden üretilebilir.
Çıkış kodu bir alt işlem başarısızken başarı sayılmaz.

### Kaldırma

Yalnız uygulama manifestindeki eşleşen paket dosyaları ve eşleşen harici
kayıtlar kaldırılır. Varsayılan olarak DataRoot korunur. Not kasası korunur.
Geniş `DelTree(DataRoot)` veya `vault.glob('*.py')` temizliği kullanılmaz.
Kullanıcı tarafından değiştirilmiş harici kayıt başka uygulamayı silecek
şekilde kaldırılmaz; sahiplik uyuşmazlığı bildirilir.

## 4. Eski kurulumdan güvenli geçiş

Geçiş varsayılanı önizlemedir. `--apply` açık seçeneği değişiklik yapar.
İşlem yeniden çalıştırılabilir; aynı oturumları/notları tekrar oluşturmaz.

1. **Envanter:** düz/nested AppData motorları, eski `.beyin` state/cache,
   gerçek kullanıcı config'i, marker, global/MCP/task/kısayol ve Inno kaydı
   okunur. Bilinmeyen dosyalar kullanıcıya ait kabul edilir.
2. **Önizleme:** her kaynağın hedefi, korunacak veri, sahipli temizleme adayı
   ve çakışma ayrı listelenir. Registry ve görev değişiklikleri de görünür.
3. **Kilitleme ve yedek:** etkin yazıcılar durdurulur. Sınırlar ve symlink/
   junction hedefleri doğrulanır. Sahipli dosyalar/config/harici kayıtlar
   DataRoot/backups/<işlem-id> altına hash manifestiyle yedeklenir.
4. **Yeni program:** AppRoot tek paket olarak stage edilir ve çalıştırılır.
5. **Veri aktarımı:** kayıtlı vault UUID'sine göre teknik state taşınır;
   cache yeniden üretilebilir, önizlemede açıkça böyle belirtilir. Kişisel
   instructions/skills overrides korunur. Yeni config legacy tercihleri alır.
6. **Bağlantılar:** yalnız etkin seçenekler yeni başlatıcıya bağlanır. Inno
   uninstall kaydı yeni AppRoot kaldırıcıya yöneltilir; eski geniş temizlik
   yapan kaldırıcı çalıştırılmaz.
7. **Doğrulama:** yeni CLI, hook, MCP, panel, indeks yolu, state tutarlılığı
   ve günlüklerin byte/hash bütünlüğü kontrol edilir.
8. **Sahipli temizlik:** yalnız tanınmış manifestle sahipliği kanıtlanan ve
   hash'i envanterden beri değişmemiş eski motor dosyaları kaldırılır.
   Klasör yalnız boşsa kaldırılır. Eski unins artefaktları ancak Inno kayıt
   sahipliği doğrulanıp yeni kayıt etkinleştirildikten sonra yedeğe alınır.
9. **Başarısızlık:** değişmiş program/config/bağlantılar geri alınır. İşlem
   sırasında başka ajanın oluşturduğu veya değiştirdiği dosya silinmez.

Teknik state'te farklı kaynaklar aynı anahtarı farklı içerikle taşıyorsa
“en yeni dosya kazanır” gibi sessiz birleştirme yapılmaz. Çakışma işlemi
etkinleştirmeden durdurur; eski kaynaklar ve notlar korunur. Aynı içerikli
kopyalar tek hedefe alınabilir. Idempotency kayıtları cache sayılıp atılmaz.

Önizleme/sahiplik doğrulaması bulunmayan mevcut temizleyici bu işlemde
kullanılmaz. Canlı RespectedOS/AppData dönüşümü uygulama planının son
devreye alma adımıdır; geliştirme ve otomatik testler geçici kasalarda yürür.

## 5. Kabul kriterleri

- Kaynakta tek `respectedbrain` paketi; kurulumda tek aktif motor dağıtımı.
- Wheel/frozen paket kaynakları ve template dahil; repo checkout'una bağımlı değil.
- Program salt okunur hedefte çalışır; AppRoot'a teknik veri yazmaz.
- Yeni kasa `.beyin`, scripts, engine, kaldırıcı veya arama DB'si içermez.
- Install/update/repair CLI ve platform kabuklarından aynı son yerleşimi üretir.
- Hook/compile/briefing/search/MCP/gateway aynı AppPaths ve UUID'yi kullanır.
- Farklı CWD, Türkçe/emoji/boşluklu yollar, seçilmiş kasa, iki kasa ve kasa
  yer değiştirme senaryolarında yanlış kasaya fallback olmaz.
- Native Windows ve açık WSL profillerinde başlatıcı/yol sözleşmeleri test edilir.
- Kapalı global/MCP/zamanlayıcı seçeneği geçişten sonra kapalı kalır.
- Gerçek kullanıcı config'i ve kişiselleştirilmiş instructions/skills korunur.
- Migration dry-run filesystem, registry, görev veya config'i değiştirmez.
- Legacy düz/nested ve kasa içi kurulumlar için veri koruma testi vardır.
- Çakışan state, yazıcı yarışı ve her aşamada enjekte edilmiş arıza rollback
  davranışıyla test edilir; kullanıcı sentinel dosyaları korunur.
- Update/migration/uninstall sırasında örnek daily, knowledge, Companion,
  proje notları ve `.obsidian` kullanıcı dosyalarının hash'leri değişmez.
- Paket tests, kaynak tests ve Windows kurulum/geri alma/harici kayıt testleri
  geçer. Atlanan platform doğrulaması açıkça raporlanır.

Eski yol testleri gerekli davranışı yeni sözleşmeyle sınar; eski klasörün
varlığını başarı sayan beklentiler aynen taşınmaz. Önceki 447 testin adedi
yeni tasarımın başarı ölçütü değildir; kapsadığı davranışların korunmasıdır.

## For future agent

Bu belgeyi ana mimari sözleşmeyle birlikte incele. Migration varsayılan olarak
önizlemedir; bilinmeyen dosya veya kullanıcı notu temizleme. Gerçek kurulum
öncesinde geçici kasalarda veri koruma ve rollback kanıtlarını tamamla.
