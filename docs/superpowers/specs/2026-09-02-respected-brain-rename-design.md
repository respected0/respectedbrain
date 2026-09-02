# Respected Brain Tam Yeniden Adlandırma Tasarımı

**Tarih:** 2026-09-02  
**Durum:** Kullanıcı tarafından onaylandı  
**Hedef sürüm:** `1.3.0`

## Amaç

Ürünün adını ve bütün güncel teknik namespace'ini `Respot Brain` / `respot` ailesinden
`Respected Brain` / `respected` ailesine taşımak. Yeni kurulum, belge, komut, görev ve üretilen
dosyalarda eski marka görünmeyecek. Buna rağmen mevcut kurulumlar veri kaybetmeden ve kişisel
notları yeniden yazmadan yeni sözleşmeye yükseltilebilecek.

## Kesin ad sözleşmesi

| Alan | Eski | Yeni |
| --- | --- | --- |
| Ürün adı | `Respot Brain` | `Respected Brain` |
| Kısa ürün/companion varsayılanı | `Respot` | `Respected` |
| GitHub repository slug | `respot-brain` | `respectedbrain` |
| Küçük harf namespace | `respot` | `respected` |
| Büyük harf namespace | `RESPOT` | `RESPECTED` |
| Global managed marker | `RESPOT-GLOBAL` | `RESPECTED-GLOBAL` |
| Antigravity hook anahtarı | `respot-brain` | `respected-brain` |
| Cursor global rule | `respot-brain.mdc` | `respected-brain.mdc` |
| Kullanıcı yedek kökü | `.respot-backups` | `.respected-backups` |
| Scheduler/yedek kökü | `.respot/schedule-backups` | `.respected/schedule-backups` |
| Sabah görevi öneki | `respot-morning-briefing-` | `respected-morning-briefing-` |
| Manifest modülü | `respot_manifest.py` | `respected_manifest.py` |
| Updater | `update_respot.py` | `update_respected.py` |
| Test environment öneki | `RESPOT_TEST_` | `RESPECTED_TEST_` |

Türkçe çekirdek yolları `.beyin/`, `.beyin-version` ve `.beyin-multi-version` marka adı değildir;
değişmeyecek. Vault adı kullanıcı tercihidir; `respectedOS` olmak zorunda değildir.

## Kapsam ve sınırlar

### Değişecek yüzeyler

- README, SETUP, Windows kurulumu, MULTI_AI ve teknik belgelerdeki güncel ürün adı ve URL'ler.
- Template'teki provider adaptörleri, generated açıklamalar, map/briefing marker'ları ve runtime
  log/thread isimleri.
- Global installer marker'ları, Antigravity hook anahtarı, Cursor rule dosyası ve yedek kökleri.
- Windows, WSL, Linux ve macOS sabah görevi adları ile schedule backup konumları.
- Updater/manifest dosya adları, importlar, test sınıfları, fixture önekleri ve environment
  değişkenleri.
- GitHub repository adı değiştirildikten sonra clone URL'leri ve yerel `origin` URL'si.

### Körlemesine değişmeyecek yüzeyler

- Kullanıcının insan tarafından yönettiği `Core.md`, `Journal.md`, `Threads.md`, günlükler ve diğer
  kişisel notlar. Bu dosyalardaki `Respot` bir ürün adı değil kullanıcının seçtiği companion adı
  olabilir.
- Git geçmişi ve daha önce yayımlanmış commit mesajları.
- Upstream/fork repository adları ve SHA referansları.
- Sağlayıcı adları ve provider-neutral fallback sırası.

Fresh template'te companion adı yine kurulum görüşmesinde sorulur. Örnek veya varsayılan gereken
yerlerde `Respected` kullanılır; kullanıcı başka bir companion adı seçebilir.

## Legacy uyumluluk mimarisi

Eski adlar bütün koda dağılmayacak. Tek bir `scripts/legacy_names.py` modülü eski marker, hook,
dosya, görev ve yedek kökü sabitlerini taşıyacak. Üretim kodunda eski marka literaline izin verilen
tek yer bu modül olacak. Migration test fixture'ları eski kurulum üretmek için bu modülü
kullanacak; belgeler ve normal runtime eski adı taşımayacak.

### Vault updater geçişi

`update_respected.py`, damgalı `1.0.0`, `1.1.0` ve `1.2.0` kurulumlarını kabul edecek.
`1.2.0 → 1.3.0` geçişi:

1. Mevcut vault'u ve platform profilini salt okunur doğrular.
2. Vault dışına mevcut transactional yedeği alır.
3. Yeni runtime ve generated dosyaları stage alanına kurar.
4. `update_respot.py` ve `respot_manifest.py` gibi eski, Respected tarafından yönetildiği kesin
   dosyaları manifest doğrulamasından sonra kaldırır; kullanıcı dosyalarına dokunmaz.
5. Adapter drift, placeholder, path containment ve syntax kapıları geçerse atomik promote yapar.
6. En son `.beyin-multi-version` değerini `1.3.0` yazar.
7. Herhangi bir hata durumunda eski kurulum ve sürüm damgası bütünüyle geri gelir.

Damgasız v1 migration aynı transaction içinde doğrudan `1.3.0` Respected Brain üretir. Tek kaynaklı
rules/skills üretimi ve symlink kullanmama ilkesi korunur.

### Global bağlantı geçişi

Yeni global installer hem `RESPECTED-GLOBAL` hem legacy marker çiftini tanır:

- Yalnız legacy çift varsa aynı konumda yeni blokla değiştirilir.
- Yeni ve legacy blok birlikte varsa işlem fail-closed durur ve çakışmayı raporlar.
- Yarım marker çifti varsa hiçbir dosya değiştirilmez.
- Antigravity'deki legacy hook anahtarı yeni anahtarla değiştirilir; unrelated hook'lar korunur.
- Cursor'daki legacy rule yalnız içeriğinin Respected tarafından yönetildiği doğrulanırsa kaldırılır.
- Claude, Codex ve Cursor hook komutları mevcut managed-command tanımıyla deduplicate edilir.
- Apply öncesi bütün hedefler gösterilir; yedek yeni `.respected-backups` köküne yazılır.

Eski yedek klasörleri otomatik silinmez. Eski kök var, yeni kök yoksa kullanıcı onaylı migration
onu yeni ada taşır. İkisi de varsa içerikler otomatik birleştirilmez; çakışmasız taşıma planı
önizlenir ve açık onay beklenir.

### Scheduler geçişi

Yeni scheduler installer yeni görev tanımını kurmadan önce aynı vault için legacy görev kimliğini
arar. Apply sırası:

1. Yeni ve legacy görev tanımlarını binary-safe/platform-doğru encoding ile sorgula.
2. Mevcut tanımı vault dışında yedekle.
3. Yeni `respected-morning-briefing-*` görevini kur ve yeniden sorgulayarak doğrula.
4. Ancak doğrulama geçerse legacy görevi kaldır.
5. Hata olursa yeni görevi kaldırıp eski tanımı geri yükle.

Aynı sözleşme Windows Task Scheduler, systemd user timer ve macOS LaunchAgent için geçerlidir.
Türkçe Windows `schtasks.exe` OEM `cp857` çıktısı bu geçişin zorunlu regresyon testidir.

Dashboard içindeki legacy briefing marker'ı okunabilir kalır; ilk başarılı yenileme onu tek bir
`RESPECTED-BRIEFING` bloğuna dönüştürür. Map dosyaları generated olduğu için yeni header ile baştan
üretilir.

## Repository ve yayın sırası

Yeniden adlandırma ayrı `1.3.0` migration sürümüdür. Önceden `1.3.0` diye kaydedilen yedi upstream
uyarlaması `1.4.0` backlog'una taşınır; böylece kurulu vault damgası gerçeği temsil eder.

Repository fork ağından kalıcı olarak ayrılacak ve bağımsız Respected Brain projesi olacaktır.
Orijinal MIT lisans bildirimi ve Git commit geçmişi korunur; README kökeni kısa ve açık biçimde
belirtir. Avenox deposu GitHub fork bağı olarak değil, push'u devre dışı bırakılmış
`avenox-reference` fetch remote'u olarak yalnız karşılaştırma/upstream audit amacıyla tutulur.

Sıra:

1. Test-first kod ve belge değişikliklerini mevcut `secondbrain` geliştirme checkout'unda tamamla.
2. Bütün platform/test kapılarını eski GitHub adıyla geçir.
3. Commit ve mevcut fork'a push için ayrı ayrı kullanıcı onayı al; uzak kopyanın doğrulanmış son
   commit'i taşıdığını kanıtla.
4. Bütün branch, tag ve referansları içeren yerel `git bundle` oluşturup `git bundle verify` ile
   doğrula; bundle yolu repository dışında olsun.
5. GitHub'ın `Leave fork network` önkoşullarını ve metadata kaybını önizle. Ayrılma için ayrıca
   açık kullanıcı onayı al; child fork veya başka engel varsa sil-yeniden-yarat yoluna otomatik
   geçme.
6. Fork ağından ayrıldıktan sonra repository'nin bağımsız olduğunu, branch/tag'leri ve Actions
   ayarlarını doğrula.
7. GitHub repository adını `respectedbrain` yapmadan önce ayrıca açık kullanıcı onayı al.
8. Rename sonrası yerel `origin` adresini `git@github.com:respected0/respectedbrain.git` yap.
   `upstream` remote'unu `avenox-reference` olarak yeniden adlandır ve push URL'sini geçersiz kıl.
9. Yeni URL'den boş geçici dizine gerçek clone yap ve fresh-install testini çalıştır.
10. Son doğrulama sonrası push için açık kullanıcı onayı al.

GitHub'ın eski URL redirect davranışı başarı ölçütü değildir; bütün güncel belgeler ve CI yeni URL'yi
kullanacaktır.

## Test stratejisi

Her davranış RED → GREEN sırasıyla geliştirilecek.

1. **Ad sözleşmesi testi:** runtime, template, public setup belgeleri ve güncel kullanıcı
   çıktılarında eski marka ailesinin bulunmadığını doğrular. Eski literal yalnız
   `legacy_names.py`, migration test/fixture'ları ve bu geçişi açıklayan açıkça işaretli tarihsel
   tasarım/senkronizasyon kayıtlarında bulunabilir; allowlist dosya ve bağlam düzeyinde sabittir.
2. **Fresh install:** portable, windows-wsl ve windows-native profilleri yalnız yeni adları üretir;
   provider adaptörleri tek canonical kaynaktan gelir.
3. **Vault update:** kişiselleştirilmiş `1.2.0` fixture'ı `1.3.0` olur; insan notları byte-for-byte
   korunur; eski managed scriptler kaybolur; hata enjeksiyonunda tam rollback olur.
4. **Global migration:** dört provider için legacy marker/hook/rule yeni ada dönüşür, unrelated
   ayarlar korunur, ikinci apply idempotenttir ve çakışma fail-closed olur.
5. **Scheduler migration:** legacy görev ancak yeni görev doğrulandıktan sonra kalkar; aktivasyon
   hatasında restore edilir; `cp857` gerçek Windows/WSL yolu test edilir.
6. **Generated drift:** template ve provider kopyaları birebir; placeholder ve eski görünür marka
   yoktur.
7. **Platform kapıları:** WSL test paketi, gerçek Windows Python/PowerShell kurulumu, Windows task
   sorgusu; Linux/macOS CI adapter testleri.
8. **Bağımsız repository kapısı:** doğrulanmış bundle, ayrılma sonrası bağımsızlık/branch/tag
   kontrolü, GitHub rename sonrasında yeni URL'den clone, README kurulum önizlemesi ve temiz
   `git status`.

## Hata ve güvenlik davranışı

- Kullanıcı notu, yedek veya global kişisel ayar açık onay olmadan silinmez.
- Yarım marker, çift yeni/legacy blok, iki yedek kökü veya doğrulanamayan legacy dosya fail-closed
  sonuç üretir.
- Migration stage ve yedekleri vault dışında kalır; path containment, reparse-point/symlink ve
  `0700`/`0600` izin sözleşmeleri korunur.
- Provider seçimi `auto` kalır; Claude, Codex, Cursor ve Antigravity'den hiçbiri zorunlu veya sabit
  provider yapılmaz.
- Commit, mevcut fork'a push, fork ağından ayrılma, repo rename, remote değişimi ve son push
  birbirinden ayrı kullanıcı onay kapılarıdır.
- Fork ağından ayrılma kalıcıdır. GitHub metadata kaybı kabul edilmeden ve doğrulanmış vault-dışı
  bundle oluşmadan işlem yapılmaz; uygunsuzlukta manuel sil-yeniden-yarat otomatik denenmez.
- Mevcut MIT lisansındaki Avenox bildirimi ve commit geçmişi korunur; bağımsızlaşma kaynak geçmişini
  yeniden yazmak için kullanılmaz.

## Kabul ölçütleri

- Yeni kullanıcı yalnız **Respected Brain** ve `respectedbrain` adlarını görür.
- Eski `1.2.0` vault, global bağlantı ve scheduler kayıp olmadan `1.3.0` olur.
- İnsan tarafından yönetilen hafıza dosyaları byte-for-byte korunur.
- Dört provider ve üç runtime profili tek-kaynak adapter üretimini korur.
- Windows native ve WSL gerçek testleri ile Linux/macOS adapter testleri geçer.
- Yeni GitHub URL'sinden fresh clone ve kurulum önizlemesi doğrulanır.
- GitHub repository'si fork ağından ayrılmış bağımsız bir repository olarak doğrulanır; bütün
  branch/tag geçmişi doğrulanmış bundle ve uzak repository ile korunur.
- Çalışma ağacında yalnız bilinçli legacy allowlist dışında eski marka kalmaz.
