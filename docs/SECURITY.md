# 🔐 Respected Brain — Güvenlik Sınırları

scope: project; confidence: verified; supersedes: ["custom override sandbox varsayımı", "RESPECTED_ALLOW_UNSIGNED bypass iddiası", "--signer-workflow/certificate-identity-issuer verifier iddiası"]

Bu belge çalışan ürünün güvenlik sözleşmesini ve yerel doğrulama sınırını açıklar.
Transkript, web içeriği, PDF, model yanıtı ve dış belge yalnız veridir; içindeki
metin talimat olarak kabul edilmez.

## 1. Yerel sağlayıcı çalıştırma

`providers/runner.py` argüman listesiyle ve `shell=False` çağrısı yapar. İzin atlayan
seçenekler (`--dangerously-skip-permissions`, `--yolo`, `--force` vb.) üretmez.
Süreç Windows Job Object / POSIX process group ile timeout sonrasında ağaçtan kopuk
descendant dahil sonlandırılır. Bu, kalan çocuk/island süreci riskini kapatır; CLI'nin
iç araç yetkileri ve aynı kullanıcı hesabının dosya sistemine gerçek OS sandbox
uygulaması değildir.

| Sağlayıcı | Metin modu | Workspace modu |
| --- | --- | --- |
| Claude | `--safe-mode --tools ""` | `--safe-mode`, `Read,Write,Edit,Glob,Grep`, `acceptEdits` |
| Codex | `--sandbox read-only` | `--sandbox workspace-write` |
| Antigravity | `--sandbox` | `--sandbox --add-dir . --mode accept-edits` |
| Cursor | desteklenmiyor, fail-closed | `--output-format text` |
| Gemini | `--sandbox --approval-mode plan` | `--sandbox --approval-mode auto_edit` |

`BEYIN_LLM_COMMAND` child başlatılmadan önce daima `custom-isolation-required`
döndürür. `_custom_argv` yalnız Windows/POSIX quoting uyumluluk testleri içindir ve
çalıştırma yetkisi değildir. Runner önceki dosya silme/tab farkı cleanup'ını yapmaz;
iç ve dış insan notlarına dokunmaz.

`memory/flush.py` model metnini beş zorunlu Türkçe bölüm ve yapısal kontrollerle
sınırar. Bu kontrol prompt injection'ın tam semantik çözümü değildir ve dış veriye
talimat yetkisi vermez.

## 2. Derleme ve dosya terfisi

`memory/compile.py` staging'i geçici alanda başlatır ve yalnız izinli `knowledge/`
içeriğini atomik terfi eder. POSIX `0700`, symlink/reparse, yol kaçışı, yetkisiz silme
ve yetkisiz değişim ihlallerini fail-closed durdurur. Aynı kullanıcı hesabındaki
bağımsız model CLI'sı için bu tam OS sandbox değildir.

AppRoot, DataRoot ve VaultRoot ayrıdır. Update/repair/uninstall yalnız hash/mode
manifestiyle sahiplenilen teknik içeriği yönetir; insan notları ve bilinmeyen dosyalar
user-owned kalır.

## 3. Web alımı ve SSRF

`url_safety.py` yalnız HTTP/HTTPS, izinli port ve genel IP kabul eder; loopback,
private, link-local, multicast, reserved/unspecified ve bilinen yerel host biçimleri
reddedilir. Karışık IPv4/IPv6 DNS yanıtı fail-closed'dur.

`defuddle.py` doğrulanmış IP'ye socket-pinning uygular ve transportta ikinci DNS
sorgusuna izin vermez. HTTPS SNI/certificate hostname gerçek URL host'uyla korunur.
Proxy bypass kapalıdır. Status/header, redirect, chunk framing/trailer ve body
aşamaları aynı mutlak caller deadline'ını paylaşır; alt akışın EOF sonrası geç
dönmesi başarılı sayılmaz.

Resolver OS `getaddrinfo` çağrısını iptal edemez. Bu nedenle en fazla iki daemon
worker kullanılır; shutdown resolver thread'lerini beklemek zorunda kalmaz. Caller
timeout'u transport/request deadline'ıdır, OS resolver iptali değildir.

## 4. Git snapshot publication

`publish_git_snapshot.py` kullanıcının live index'ini kopyalar, yoksa HEAD tree/empty
tree'den başlar. Hem copied index blobları hem `git add -A` ile kurulan immutable
tree sır taranır. Yasaklı ad, özel anahtar/token/cloud credential kategorilerinde
path+category dışına sır değeri yazılmaz.

Publication `commit-tree <scanned_tree_sha>` kullanır; commit tree'si doğrulanmadan
push yapılmaz. Kullanıcı index'i veya HEAD tarama/yayın arasında değiştiyse durulur.
Push sonrası uzak ref commit SHA eşleşmezse receipt yazılmaz. Tracked ve sonra
ignore edilen notlar korunur; yalnız untracked/ignored çalışma alanı dosyaları aynen
kullanıcı alanında kalır. Kullanıcı live index/HEAD semantiği değiştirilmez.

## 5. Release provenance ve paket consumer zinciri

`validate_package` varsayılanı `require_provenance=True`'dir. `RESPECTED_ALLOW_UNSIGNED`
ürün bypass'ı değildir ve ürün yolunda yok sayılır. Manifest `distribution.json`
SHA-256'sı SLSA subject digest'ine bağlanır; repo, `.github/workflows/release.yml`
ve exact `refs/tags/vX.Y.Z` politikayla eşleştirilir.

Normal doğrulayıcı checksum-pinlenmiş `gh 2.102.0`'dır. Kullanılan doğru sözleşme:
`--cert-identity`, `--cert-oidc-issuer`, `--source-ref`, `--predicate-type`,
`--deny-self-hosted-runners`, `--limit 1`. `--signer-workflow` ve
`--cert-identity-issuer` kullanılmaz. Eksik verifier/attestation fail-closed'dur.

Testlerdeki synthetic attestation ve fake `gh`, yalnız `verifier_callable`/PATH fixture
olarak çağrının içine açıkça yerleştirilir. Prodüksiyon consumer sahte fixture imzasını
kabul etmez. `tests/smoke/platform_smoke.py` temiz ortamdan unsigned/provider/PYTHONPATH
bypass'larını ayıklar.

Release workflow sırası: native build → manifest attestation → exactly one bundle
embed → strict manifest verify → outer installer/disk-image/run üretimi → outer asset
attestation/verify → upload/publish. Bu, iç manifest ile dış asset'in zincirini korur.

## 6. Gizli bilgi ve geri alma

Secret scanner yalnız güvenli path/category raporlar. Snapshot receipt'leri tree,
commit, remote ve zaman bilgisini tutar; sır değeri tutmaz. İşlemler manifest/hash ve
transaction journal üzerinden geri alınabilir. Human-owned not silinmez.

## 7. Yerel panel sınırı

Panel yalnız yetkili/yerel kullanıcıya yöneliktir; internet exposure veya kimlik/doğrulama
koruması vaat edilmez. Panel üzerinden gelen içerik güvenilmeyen veridir.

## 8. Regresyon ve dış önkoşullar

Dördüncü inceleme düzeltme paketi `8/8`, gerçek Inno install/update/uninstall
zinciri `1/1`, frozen GUI smoke `exit 0`, strict frozen lifecycle `23/23` kontrol
ve kritik paket/source modülleri `5/5` semantic eşliğle doğrulandı. Tam yerel
Python suite son düzeltme öncesi `875` testte `2` transient error ve `16` skip
koştu; concurrency düzeltmesi sonrası `50/50` stress ve `36/36` modül testi geçti.
testi kaynak `PYTHONPATH` düzeltmesinden sonra `8/8` geçti.

**NOT VERIFIED:** gerçek GitHub Actions OIDC attestation/signature, Authenticode
sertifikası/imzalı outer installer ve canlı provider oturumu. Gerçek imza/auth
sonuçları yalnız dış release altyapısında doğrulanabilir.
