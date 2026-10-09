# 🛡️ Karar: Güvenlik Sertleştirme Zinciri — 2026-10-07 Revizyonu

scope: project; confidence: verified; supersedes: ["2026-10-06 dört güvenlik sertleştirme kararı", "üçüncü inceleme öncesi provider/custom, snapshot publication ve unsigned bypass varsayımları"]

## 1. Bağlam

`SECURITY_HARDENING_CODEX_THIRD_REVIEW.md` beş güvenlik/işlevsellik bulgusu verdi:
izinli görünen provider süreçlerinin yeterince sınırlandırılmaması, custom child'ın
izolasyon yokken başlatılması, scan sonrası mutable index yarışı, imzasız paket
bypass'ı/yanlış verifier sözleşmesi ve HTTP status/chunk framing deadline boşluğu.
Ayrıca takip edilen ancak `.gitignore` içindeki notların snapshot'tan düşmesi ve
dondurulmuş paketteki kritik modüllerin güncel kaynakla eşleşmemesi kanıt riski idi.

Dördüncü bağımsız inceleme bu zincire dört yeni bulgu ekledi: ikinci normal
snapshot'ın non-fast-forward ile yayımlanamaması, geç header byte sonrası duran
HTTP bağlantısında mutlak deadline'ın aşılması, frozen GUI'de Tcl/Tk runtime
eksikliği ve eski snapshot implementation'ının ölü kod olarak kalması. Bu karar,
o dört bulgunun kapanışını da kapsar.

## 2. Kararlar

### A. Provider ağacı ve custom sınırı
- Tanımlı provider'lar desteklenen CLI bayraklarıyla çağrılır ve Windows Job
  Object / POSIX process group üzerinden süreç ağacı ile birlikte sonlandırılır.
- Timeout, nonzero çıkış, kısmi stdout/stderr ve kopuk/detached descendant
  davranışları kalıcı regresyon testleriyle korunur.
- `BEYIN_LLM_COMMAND` için doğrulanmış bir OS sandbox sözleşmesi bulunmadığından
  child başlatılmadan önce koşulsuz `custom-isolation-required` ile fail-closed
  olunur. `_custom_argv` yalnız komut ayrıştırma/Windows quoting uyumluluğu için
  korunur; çalıştırma yetkisi vermez.
- Dosya silme/rollback tabanlı yapay sağlayıcı temizliği geri getirilmez.

### B. Immutable snapshot publication
- Yayım öncesi kullanıcı index'i kopyalanır; index yoksa HEAD tree'si, HEAD de
  yoksa boş tree başlangıcı kullanılır. Bu, takip edilen ve ignore listesine sonradan
  girmiş notları korur. Ignore edilmemiş çalışma alanı içeriği snapshot'a eklenir;
  yalnız untracked/ignored kullanıcı dosyaları aynen kullanıcı alanında kalır.
- Kopyalanan index blobları, ardından `git add -A` ile üretilen gerçek tree
  ayrı ayrı sır taranır. Tarama sonrası tree değiştirilemez; yayımlanan commit
  `commit-tree <tree_sha>` ile tam olarak taranmış tree'ye bağlanır ve commit tree'si
  yeniden doğrulanır.
- Kullanıcı live index'i veya HEAD'i işlem sırasında değiştiyse hiçbir commit/push
  yapılmaz. Push sonrası uzak ref commit SHA'sı doğrulanır, receipt yalnız eşitlikte
  yazılır. Staging ve HEAD semantiği değiştirilmez.

### C. Release provenance ve paket consumer zinciri
- Ürün kodu `validate_package(require_provenance=True)` varsayılanını korur.
  `RESPECTED_ALLOW_UNSIGNED` veya başka ortam değişkeni prodüksiyon bypass'ı değildir;
  ürün yolunda yok sayılır.
- Test fixture politikası yalnız test sürücüsü tarafından açıkça enjekte edilen
  `verifier_callable` dikişidir. Normal frozen kurulumda sahte fixture imzası kabul
  edilmez; eksik ya da kriptografik olarak doğrulanmamış attestation fail-closed'dur.
- Release akışı önce `distribution.json` manifest'ine SLSA attestation üretir, tek
  bundle'ı indirip `distribution.json.attestation.json` adıyla pakete yerleştirir,
  sonra consumer doğrulaması yapar. Dış release asset'leri ayrıca attest edilir ve
  doğrulanır.
- Sabit doğrulayıcı `gh 2.102.0`'dır; release workflow arşiv hash'iyle indirir ve
  gerçek CLI yardımında da aynı destek sözleşmesi test edilir. Argv:
  `--cert-identity`, `--cert-oidc-issuer`, `--source-ref`, `--predicate-type`,
  `--deny-self-hosted-runners`, `--limit 1`. Çakışan `--signer-workflow` kullanılmaz.

### D. HTTP mutlak deadline ve resolver kapasitesi
- `_DeadlineReader` status/header, chunk-size/framing/trailer ve body/TLS
  aşamalarındaki bloklamaları aynı caller deadline'ına bağlar. Alt akışın deadline
  sonrası EOF/dönüş yapması başarılı kabul edilmez.
- `getaddrinfo` iptal edilemeyen OS çağrısı olduğu için iptal ediliyormuş gibi
  anlatılmaz. Bunun yerine en fazla iki daemon worker ile kapasite sınırı ve process
  kapanışını beklemeyen shutdown sözleşmesi vardır; caller süresi yine mutlak
  request deadline'ını uygular.

### E. Dördüncü inceleme kapanışı
- Snapshot zinciri, kullanıcı HEAD/index durumunu değiştirmeden receipt üzerinden
  alınan `remote_parent` ile ilerler; ikinci ve sonraki yayımlar fast-forward
  zincirini korur.
- `_DeadlineReader` her bloklayan okuma öncesi kalan mutlak süreyi sokete uygular;
  geç byte sonrası idle bağlantı eski socket timeout'unu beklemez.
- Frozen build `_tkinter.pyd`, Tcl ve Tk runtime dizinlerini paketler; wizard
  başlamadan önce `TCL_LIBRARY` ve `TK_LIBRARY` forward-slash olarak ayarlanır.
- Eski, çağrılmayan snapshot implementation bloğu kaldırılmıştır.

## 3. Doğrulama kararı

- Odak provider/provenance/HTTP/process regression paketi `22/22` geçti.
- Frozen paket/source semantic karşılaştırması beş kritik modülün opcode, sabit,
  çağrı, argüman ve nested code düzeyinde `5/5` eşleştiğini doğruladı.
- Temiz ortam strict fixture-provenance yaşam döngüsü `23/23` kontrolle geçti:
  setup, repair, iki update, deferred update/receipt, turn upsert ve owned uninstall.
- Yeni tam unittest/per-test kanıtı `records/2026-10-security-hardening/IMPLEMENTATION.md`
  ve final local handoff raporundadır; eski `FINAL_*` sayıları yeni paket kanıtı
  olarak kullanılmaz.
- Dördüncü inceleme düzeltme paketi `8/8` test, gerçek Inno zinciri `1/1`,
  frozen GUI smoke `exit 0` ve package/source semantic compare `5/5` ile geçti.
  Tam Python suite son concurrency düzeltmesi öncesi `875` testte `2` transient
  error verdi; düzeltme sonrası `50/50` stress ve `36/36` modül testi geçti.
  Ayrıntılı kanıt tablosu
  `records/2026-10-security-hardening/FOURTH_REVIEW_REMEDIATION.md` içindedir.
## 4. Dış önkoşullar

Gerçek GitHub OIDC/Sigstore attestation'ı, Authenticode sertifikası ve GitHub tag
yayını yerel kaynak değişikliğiyle üretilemez. Bu ortamda gerçek imzalı bundle
doğrulaması ve imzalı Windows installer **NOT VERIFIED**dır. Frozen GUI ve gerçek
Inno zinciri bu teslimde yerel olarak doğrulandı; canlı provider oturumu ve dış
release altyapısı ayrı dış kabul konusudur.
