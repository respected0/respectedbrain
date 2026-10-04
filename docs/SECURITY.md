# Respected Brain — güvenlik sınırları

scope: project; confidence: verified; supersedes: [önceki scripts tabanlı güvenlik açıklaması]

Bu belge 2026-10-04 kaynak ağacındaki korumaları ve sınırlarını açıklar.
Tasarım kaynağı [modüler temel](superpowers/specs/2026-10-03-modular-foundation-design.md),
çalıştırılmış test kanıtı [doğrulama raporudur](superpowers/verification/2026-10-04-modular-foundation.md).
Transkriptler, günlükler, web içeriği ve model yanıtları güvenilmeyen veridir.
Modelin talimatlara uyması veya bir isteği reddetmesi güvenlik sınırı sayılmaz.

## Yerel sağlayıcı çalıştırma

`src/respectedbrain/providers/runner.py` sağlayıcıları argüman dizileriyle,
`shell=True` kullanmadan çağırır. Bu uygulamanın shell string birleştirmesinden
kaynaklanan enjeksiyonu önler; çağrılan CLI'ın araçlarını veya ayrıcalıklarını
ortadan kaldırmaz. Kullanıcının `BEYIN_LLM_COMMAND` override'ı da güvenilen
kullanıcı yapılandırmasıdır ve ayrıca bir sandbox sağlamaz.

Sağlayıcıların yetki kontrolleri aynı değildir:

| Sağlayıcı | Metin modu | Derleme/workspace modu |
| --- | --- | --- |
| Claude | `--safe-mode --tools ""` | `--safe-mode`, yalnız `Read,Write,Edit,Glob,Grep`, `acceptEdits` |
| Codex | `--sandbox read-only` | `--sandbox workspace-write` |
| Antigravity | `--sandbox` ve `--dangerously-skip-permissions` | `--add-dir . --mode accept-edits` ve `--dangerously-skip-permissions` |
| Cursor | Açık sandbox veya araç kapatma bayrağı verilmez | `--force` |
| Gemini | Açık sandbox bayrağı verilmez | `--approval-mode auto_edit` |

Bu tablo uygulamanın ürettiği argv'yi gösterir; kurulu CLI sürümünün bayrakları
nasıl uyguladığını veya bütün sağlayıcıların eşdeğer izolasyon sunduğunu
kanıtlamaz. Cursor/Gemini metin modu için uygulama araç yetkilerinin kapalı
olduğunu garanti etmez. Derleme sağlayıcısının erişimi, kendi sandbox/izin
mekanizmasına ve kullanıcı hesabının işletim sistemi yetkilerine bağlıdır.

`memory/flush.py` model metnini beş sabit Türkçe bölüm ve ek içerik kontrolleriyle
sınar; reddedilen çıktı günlük özeti olarak yazılmaz. Biçim doğrulaması tek
başına bütün anlamsal prompt injection girişimlerini saptayan bir mekanizma değildir.

## Derleme ve dosya terfisi

`src/respectedbrain/memory/compile.py` derlemeyi aktif kasa yerine geçici bir
staging dizininde başlatır. POSIX'te staging için `0700` uygulanır. Bu izin,
başka kullanıcıların erişimini sınırlar; aynı kullanıcı hesabında çalışan bir
model sürecinin bütün dosya sistemine erişmesini engelleyen OS sandbox değildir.
Windows'ta POSIX mode bitleri aynı erişim garantisini vermez.

Staging'den kasaya terfi için izin verilen içerik:

- `knowledge/index.md` ve `knowledge/log.md`
- `knowledge/concepts/*.md`
- `knowledge/connections/*.md`

Kod staging dosyalarını, izin dışı değişiklikleri, silmeleri, symlink/reparse
point ve yol kaçışlarını kontrol eder. İhlal terfiyi durdurur. Bu kontrol,
uygulamanın yaptığı terfiyi sınırlar; bağımsız olarak yeterli yetkiye sahip
sağlayıcı sürecinin staging dışında yazmasını önleyen bir sandbox değildir.
Kasa yazıcıları UUID bazında ortak kilit protokolünü kullanır.

## Web alımı ve SSRF

`src/respectedbrain/maintenance/ingestion/url_safety.py` HTTP/HTTPS, port 80/443,
kimlik bilgisiz URL ve genel IP adresi kontrollerini uygular. Loopback, özel,
link-local, multicast, reserved/unspecified adresler ve bilinen yerel host
biçimleri reddedilir. DNS yanıtlarındaki adresler de kontrol edilir.

`defuddle.py` ilk URL'yi ve yönlendirme hedeflerini yeniden doğrular, indirme
süresi ve byte sayısını sınırlar. Yönlendirme sayısı `urllib` davranışına
bağlıdır; uygulama özel bir beş-yönlendirme sınırı koymaz.

**Sınır:** Doğrulamada çözülen IP, sonraki `urllib` bağlantısına sabitlenmez.
Bağlantı sırasında DNS yeniden çözülebilir; DNS rebinding'e karşı tam koruma
iddiası yoktur. DNS çözülememesi varsayılan `require_resolvable=False` ile
tek başına red sebebi değildir. `urllib` ortamın proxy ayarlarını da kullanabilir.
Bu alanın sertleştirilmesi için bağlantıda doğrulanmış adres/peer kontrolü ve
uygun proxy politikası gerekir; mevcut testler böyle bir transport garantisi
sağlamaz.

## Kurulum, güncelleme ve kaldırma

Native paket `distribution.json` içindeki SHA-256 envanteriyle doğrulanır.
Yol ve sahiplik kontrolleri, işlem günlüğü ve byte yedekleri kurulum servislerinde
uygulanır. Hash envanteri paket içi tutarlılıktır; yayıncı kimliğini doğrulayan
bir dijital imza değildir. Paket ve manifest birlikte değiştirilebilirse yalnız
hash kontrolü güvenilir kaynağı kanıtlamaz.

İşlem journal'ları ve yedekleri `DataRoot/backups/<işlem>/` altında tutulur;
eski `scripts/update_respected.py` ve `~/.respected-brain-yedek/` düzeni güncel
ürün sözleşmesi değildir. Kaldırma sahipliği kanıtlanan teknik dosyaları hedefler,
not kasası hedef değildir. Kullanıcı sonradan dosyayı değiştirmişse hash
uyuşmazlığı conflict olarak korunur. Migration varsayılan olarak önizlemedir;
`--apply` değişiklik yapar. Setup/update/uninstall aynı varsayılan preview
sözleşmesine sahip değildir.

## Gizli bilgiler ve yedekler

Kök `.gitignore` `.env` biçimlerini, anahtar/sertifika dosyalarını, yerel ayarları,
yedekleri ve çalışma çıktılarını dışlar. Ignore kuralları zaten takip edilen
bir sırrı geçmişten çıkarmaz ve not gövdesindeki anahtarları tespit etmez.
`maintenance/vault_linter.py` ve paketlenmiş `beyin-doktor` ayrıca hijyen
kontrolleri sunar; bunlar eksiksiz secret tarayıcısı değildir.

İsteğe bağlı Git snapshot aracı `maintenance/backup/publish_git_snapshot.py`
dosya adlarına göre bir secret guard uygular ve `--apply` ile `git add .`, commit,
push çalıştırır. Bu işlem not gövdesindeki sırları taramaz ve dışlanmış dizinlerdeki
önceden takip edilen içerikler için tam koruma sağlamaz. Önizleme commit/push
çalıştırmaz; dal durumunu okumak için `git fetch` çalıştırabilir.

## Regresyon kanıtı

`tests/scripts_test.py`, `tests/zero_trust_security_test.py`,
`tests/backup_and_snapshot_test.py`, `tests/vault_hygiene_test.py` ve
`tests/foundation_*test.py` ilgili davranışları sınar. Testlerin geçtiği host,
paket ve atlamalar tarihli doğrulama raporlarında belirtilir. Simülasyon veya
CI matrisinin varlığı, fiziksel host/oturum açmış sağlayıcı kanıtı değildir.
