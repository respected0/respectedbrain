# Modüler temel doğrulaması — 2026-10-04

scope: project; confidence: verified; supersedes: []

Tasarımın tek kaynağı [onaylı sözleşme](../specs/2026-10-03-modular-foundation-design.md),
görev durumu [uygulama planı](../plans/2026-10-03-modular-foundation.md).
Bu dosya test kanıtı ve canlı envanter raporudur.

## Doğrulama

| Kontrol | Kanıt |
| --- | --- |
| Bütün kaynak regresyonları | 627 test, 265.956 s, OK (15 atlandı). |
| Gerçek Windows Inno + kullanımda executable + ACL | 3 test OK, 616.624 s; final kaynak algoritmasıyla PowerShell kapısından tekrar 3 test OK, 659.925 s. |
| Paket talimatları ve rehberler | 11 test OK, 0.964 s; yanlış marker adı için önce RED, düzeltme sonrası GREEN. |
| Bağımsız son inceleme | Paket/ownership/rollback incelemesinde açık Critical/Important yok; son 5 paket talimat testi bağımsız OK. |
| Wheel | Son resource içeriğiyle build OK; checkout dışındaki izole venv'de version, marker ve seed kaynak kontrolü OK. |
| Frozen komutlar | Son resource paketiyle sistem Python'u PATH dışında, checkout dışında version/registry/maps/search/hook/MCP OK. |
| Windows launcher | 7 native test OK, 8.404 s; final frozen protokol kontrolü de OK. |
| Windows zamanlayıcı | 14 test OK, 14.562 s; benzersiz geçici Task/shortcut/HKCU kayıtları temizlendi. |
| Fiziksel Windows smoke | Final paketle 17/17 VERIFIED; iki günlük turn aynı oturum girdisini güncelledi, iki update günlük byte'larını korudu, uninstall kullanıcı dosyası/not/state'i korudu ve eski kullanıcı bağlantısını geri koydu. |
| Git Bash | Hook fixture'ları 8/8 OK; yerel upstream Git fixture'ları 9/9 OK. Dış upstream ağı kullanılmadı. |

Kaynak keşfi `unittest discover -s tests -p '*test*.py'` ile yapılır. Üç uzun
native kurulum senaryosu ayrı, sabit dağıtım üzerinde çalıştırılır; diğer keşfedilen
testler aynı kaynak ağacında çalışır. Böylece aynı native dosyalar test sırasında
yeniden derlenmez. Paket talimat düzeltmeleri ürün algoritmasını değiştirmez;
son resource içeriği ayrı sözleşme ve frozen kontrollerle doğrulanır.

15 atlama: kullanıcı tarafından kaldırılmış eski `.orchestration` fixture'ları 2;
POSIX/Linux fiziksel çalışması veya flock/izin modeli isteyen 5; Windows symlink
ayrıcalığı bulunmayan 8. Atlamalar başarı sayılmaz.
Linux/macOS/gerçek WSL fiziksel çalışması bu makinede doğrulanmadı;
CI matrisi ve simülasyon testleri fiziksel kanıt yerine geçmez. Python 3.10
çalışması CI kapısıdır; bu yerel çalışmanın Python sürümü 3.13'tür.

## Native senaryoların sınadığı davranış

- Türkçe/emoji içeren geçici program, veri ve kasa yollarında gerçek kurulum ve
  tekrar kurulum; benzersiz test registry kaydı; yalnız `unins000.exe/.dat` çifti.
- Windows uygulamalar listesine kaydedilmiş komutla kaldırma; özel DataRoot/VaultRoot
  yolları ortam override'ı olmadan korunur. Kullanıcı notu, bilinmeyen program dosyası
  ve varsayılan teknik veri kalır; yalnız sahipli program ve registry kaydı kaldırılır.
- Kurulu executable çalışırken update, doğrulanmış OS-temp helper'a devredilir.
  Hatalı paket sürümü health kontrolünde geri alınır; eski program/not hash'leri eşittir.
  Geçerli update son makbuzda başarılıdır. `pending` tamamlanma iddiası değildir.
- AppRoot'a yazma gerçek Windows ACL ile engellenir; arama çalışır, index DataRoot'a
  yazılır ve program hash'leri değişmez.

## Uygulama sırasında netleşen sözleşmeler

- Composition root `respectedbrain/bootstrap.py` olur; `core` feature modüllerini
  import etmez. Global ayarlar tek `integrations/global_config.py` modülündedir.
- Bağımsız not yazıcıları UUID shared lease alır. Aktivasyon önce admission kilidi,
  ardından exclusive quiesce alır. Windows'ta kilit dosyasına ilk byte yazmak yarış
  oluşturduğundan sıfır uzunluktaki dosyanın kendisi kilitlenir; gerçek süreç testi geçti.
- Uzun staging DataRoot'tadır; atomik son not değişimi için notun diskinde kısa
  geçici dosya gerekir. Kalıcı teknik durum kasaya yerleşmez.
- Inno payload'ı yalnız OS-temp'e açar; AppRoot dosyalarını ortak transaction servisi
  yönetir. `UninstallLogMode=overwrite` tekrar kurulumda aynı sahipli kaldırıcı çiftini korur.
- Inno kaldırma başlamadan `.dat` dosyasını exclusive açar. Registered launcher önceden
  byte hash ve dosya kimliğiyle kanıt oluşturur; callback bu kanıtı transaction kilidi
  altında doğrular. Yalnız kilitli `.dat` için değişmemiş kimlik kanıtı kullanılabilir.
  Header veya dosya adı tek başına sahiplik değildir.
- Kaldırma baseline'ı transaction rollback baseline'ından ayrıdır: kaldırma eski yönetilen
  hook/task kayıtlarını yeniden canlandırmaz; kullanıcı ayarları ve notify zinciri korunur.

## Canlı bilgisayarın salt okunur önizlemesi

`migrate --legacy-root <eski DataRoot> --vault <RespectedOS>` komutunda `--apply`
verilmedi. Parser ve dispatch kaynakları bunun salt okunur yol olduğunu doğrular;
sıfır yan etki testi ayrıca 1/1 OK oldu. Canlı önizleme öncesi/sonrası mevcut AppRoot,
DataRoot, kasa ve Codex config içindeki **1354 dosyanın SHA-256 envanteri eşit**.
Bu ölçüm registry/task byte snapshot'ı iddiası değildir.

Önizleme 321 kayıt bildirdi: 216 kullanıcı dosyasını koru, 81 teknik state kopyalama
adayı, 18 kişisel override, 3 config birleştirme, 1 cache yeniden kurma ve 2 yalnız
sahipliği kanıtlanan artık adayı. Bunlar yapılmış işlem değil, plan girdileridir.
Global/MCP/schedule/shortcut tercihleri dört ayrı `false` olarak kaldı.

Üç engel var:

1. AppData runtime state ile kasadaki eski engine state farklı `health.json` içeriyor;
   ayrıca şemaları farklı. Tek dosyaya sessizce ezilerek birleştirilemez.
2. Aynı eski kasa anahtarı için `session_start_time` farklı. Kasadaki kopya hâlen aktif
   eski oturum tarafından güncelleniyor; birleştirme ve yazıcı kesme politikası gerekir.
3. Codex `notify` komutu bilgisayar kullanım eklentisinin executable'ıdır; eski motor
   komutu `--previous-notify` içine zincirlenmiştir. Mevcut ownership denetimi bu dış
   wrapper'ı ürünün kendi komutu kabul etmez. Eklenti bağlantısı korunmalıdır.

İlk önizlemedeki prompt counter farkı sonraki salt okunur ölçümde yoktu; eski yazıcı
aktifken state değişebildiğinin kanıtıdır. Rastgele bir kopyayı seçmek veya geniş
temizlik yapmak uygulanmadı. Tam JSON raporları kişisel config içerebildiğinden Git'e
eklenmez; yalnız ignored çalışma kanıtı alanında tutulur.

Gerçek kurulum/migration **uygulanmadı**. Eski uninstaller çalıştırılmadı, kasa taşınmadı.
Bu önizlemenin eski veriyi aktaran yolu üç çatışmayı çözen plan gerektiriyordu.
Kullanıcının güncel devreye alma tercihi [ana plandadır](../plans/2026-10-03-modular-foundation.md#kullanıcının-devreye-alma-kararı--2026-10-04);
bu tarihsel önizleme yeni kasa seçiminin önkoşulu olarak okunmamalıdır.

## Bilinen sınırlar

Native taze kurulumu bu makinede yaklaşık 113 saniye sürmüş ölçüm vardır. Transaction
journal'ının her dosyada yeniden yazılması I/O maliyeti oluşturuyor. Native fixture
timeout'u 300 saniyedir; timeout olursa yalnız fixture'ın bilinen alt süreç ağacı
kapatılır. Journal performans iyileştirmesi bu temel geçişin dışında ayrı iştir.
Doğrulanmış helper kopyaları OS-temp'te tutulur; DataRoot aktif executable içermez.

Birleştirme öncesinde ana checkout başlangıçtaki kullanıcı değişiklikleriyle korundu;
iş `codex/modular-foundation` dalında ayrı managed worktree'de hazırlandı.
Ana dala bütünleştirme ve canlı kurulum ayrı kararlardır; güncel durum uygulama planındadır.
Başlangıçta alınan 41 kullanıcı dosyası hash'i kapanışta tekrar karşılaştırıldı; fark yok.

## Yerel birleştirme — 2026-10-04

Kullanıcının `yap onaylıyorum` mesajıyla yerel birleştirme onaylandı. `main`,
`1d27391` commit'inden `3b45460` commit'ine `--ff-only` ile ilerletildi; çatışma olmadı.
Ana proje `C:/Users/Furkan/Documents/ChatGPT/secondbrain` konumundadır.
GitHub'a push ve gerçek ürün kurulumu yapılmadı.

Önceki 41 değişik dosya, modüler çalışma başlamadan taşınmış baseline ile tekrar
karşılaştırıldı: fark veya yeni dosya yoktu. Eski yapıyı yeniden canlandıracak bir
stash pop uygulanmadı. 41 birebir byte yedeği SHA-256 ile tekrar doğrulandı;
geri dönüş Git stash kaydı da korunuyor. Yedeklerin konumu Git'ten dışlanan
`.superpowers/sdd/2026-10-04-local-integration/` alanıdır.

Worktree'nin ignored deney/test kanıtları ana projeye kopyalandı ve 1290 dosyanın
hash eşitliği doğrulandı. Native dağıtım ana projenin `dist/` alanına kopyalanıp
package manifest'i doğrulandı. Main'deki geliştirme venv'i yeni ana proje kaynağına
editable bağlandı; import yolu doğrudan ana projenin `src/` alanıdır.
Bu işlem bilgisayara ürün kurulumu değildir.

Ana klasörde frozen version/registry/maps/search/hook/MCP kontrolü OK oldu.
Ana klasördeki son tam komut `python -m unittest discover -v -s tests -p '*test*.py'`:
**630 test, 482.274 s, OK (skipped=15)**. Bu tek koşu gerçek Windows native kurulum,
update rollback ve readonly AppRoot senaryolarını da içerir. Ana klasörde Git Bash
hook fixture'ları 8/8 OK, yerel upstream fixture'ları 9/9 OK oldu.

İlk tam koşuda yalnız detached-process fixture'ı cleanup sırasında Windows log kilidine
takıldı. Testin `done` dosyası süreç sona ermeden yazılıyordu. Bu yarış, child'ın dosyayı
yazdıktan sonra kısa süre yaşamaya devam ettiği fixture ile yeniden üretildi (RED).
Test artık Windows'ta child PID'nin gerçekten sonlanmasını bekler; ürün algoritması
değişmedi. İlgili 4 test GREEN oldu; yukarıdaki son tam koşuda da hata kalmadı.

Native paket/installer/wheel ve ignored kanıtlar korunduktan sonra managed worktree,
Codex'in geri alınabilir archive işlemiyle arşivlendi. Artifact `archived_worktree` olarak
doğrulandı; `git worktree list` yalnız ana projeyi gösterir. Kişisel not kasası ve canlı
ürün kurulumu bu birleştirmenin hedefi olmadı.

## For future agent

Önce ana planın güncel devreye alma kararını ve bu tarihsel kanıtı oku.
Eski veri aktarımı seçilirse state çakışmalarını zorla aşma; dış Codex wrapper bağlantısını koru.
Test paketini derlerken eşzamanlı native test çalıştırma. Test başarılarını gerçek
kurulumun uygulanmış olmasıyla karıştırma; not kasasının mevcut konumu korunur.
