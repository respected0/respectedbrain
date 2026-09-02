# Upstream senkronizasyon kaydı

Bu dosya Respected Brain'in `avenoxai/avenoxbeyin` ve ilgili fork değişikliklerini nasıl
değerlendirdiğini kaydeder. Amaç kör merge değil; doğrulanmış davranışı provider-neutral Respected
katmanına uyarlamak ve sonraki incelemede aynı analizi tekrarlamamaktır.

## Politika

1. Önce `./scripts/upstream_sync.sh check` ile yeni upstream commitleri listelenir.
2. Her commit davranış ve test düzeyinde incelenir; yalnız dosya benzerliğine bakılmaz.
3. Claude-only kod, Respected'ın Claude/Codex/Cursor/Antigravity model seçimini geriletemez.
4. Güvenlik, kullanıcı hafızasını koruma, WSL köprüsü ve tek-kaynak adapter üretimi korunur.
5. Alınan davranış için önce başarısız regresyon testi yazılır; tam test kapısı geçmeden yayınlanmaz.
6. Büyük platform veya yedekleme mimarileri çekirdek bug fixi gibi cherry-pick edilmez; ayrı tasarım
   ve platform doğrulaması ister.

## 2026-08-28 incelemesi

| Kaynak | İncelenen uç | Karar | Gerekçe |
| --- | --- | --- | --- |
| `avenoxai/avenoxbeyin` `main` | `18c83ff` | Seçerek uyarla | Göktaş compile düzeltmeleri ve Morp1e Windows portu upstream'e girmiş durumda. |
| `goktas-batuhan/fix/compile-trigger-reliability` | `2331ee2`, `5fed9f6` | **Alındı ve uyarlandı** | Başarılı trigger claim sızıntısı, kaçırılan akşam derlemesi ve kısmi bugünün erken ingest edilmesi gerçek platform-bağımsız hatalardı. Respected'ın `_run_model` ve Antigravity transkript desteği korunarak taşındı. |
| `morp1e/windows-support` | `ac207ee` | **Davranış seçilerek alındı** | PowerShell preflight, native lock/process ihtiyaçları ve Windows CI dersleri provider-neutral kurucuya uyarlandı. Claude zorunluluğu, `_run_claude` ve ayrı PowerShell lifecycle kopyaları alınmadı. |
| `enesadakli/windows-native` | `920b597` | **Temel parçalar alındı** | Native Python lifecycle, reparse-point güvenliği ve installer test yaklaşımı tek ortak runtime'a uyarlandı. Immutable event log, genişletilmiş doctor ve Restic/DPAPI yedekleme ayrı projeler olarak ertelendi. |

### Bu turda alınan davranış

- SessionEnd sonrası başarılı compile, `compile-trigger-YYYY-MM-DD` claim'ini mutlaka bırakır.
- SessionStart bağlam çıktısından sonra ayrık `--maybe-compile` catch-up çağrısı yapar.
- Catch-up yalnız tamamlanmış önceki günleri seçer; bugünün daily dosyası `--before-date` ile dışarıda
  kalır. Bu sınır SessionStart saat 18:00'den sonra açılsa bile korunur; upstream patchindeki saat
  koşulu Respected'ta bu köşe durumuna göre sıkılaştırıldı.
- Saat 18:00 sonrası normal SessionEnd davranışı değişmez.
- Model çalıştırma hâlâ provider-neutral `model_runner.py` üzerinden yapılır.

### Provider-neutral native Windows temeli

`5cc4c36` commit'iyle forkların yararlı Windows davranışı Respected mimarisine uyarlandı:

- Claude/Codex/Cursor/Antigravity için tek `lifecycle.py`; POSIX hook'lar yalnız ince launcher;
- POSIX `fcntl` ve Windows `msvcrt` kullanan ortak kilit, detached process ve path containment API'si;
- `portable`, `windows-wsl`, `windows-native` olmak üzere üç deterministik profil;
- `py.exe -3` ve mutlak Windows bridge yolu kullanan proje/global adaptörleri;
- Claude gerektirmeyen PowerShell 5.1 uyumlu taze kurucu ve `1.0.0 → 1.1.0` transactional updater;
- gerçek Windows PowerShell kurulum testi ve Windows Python süreçlerinde dört provider lifecycle,
  concurrency, detached flush, quota fallback ve current-day catch-up sınırı;
- `.github/workflows/windows.yml` içindeki `windows-latest` release kapısı. Commit `5855918` için
  [windows-native #33209497580](https://github.com/respected0/respectedbrain/actions/runs/33209497580)
  42 saniyede geçti; PowerShell fresh-install ve native lifecycle/runtime adımları yeşil.

### Bilinçli olarak alınmayanlar

- Upstream PowerShell hook dosyaları ve Claude-only Windows installer doğrudan kopyalanmadı; aynı
  ihtiyaç tek Python lifecycle ve provider seçmeli Respected kurucusuyla karşılandı.
- Enes dalındaki Restic/DPAPI yedekleme otomatik etkinleştirilmedi.
- Immutable bridge event log ve git-geçmişine dayalı doctor kontrolleri bu bug-fix turuna eklenmedi.
- Damgasız v1 vault'un native Windows migrasyonu açılmadı; doğrulanmış WSL transaction korunuyor.

## Sonraki inceleme

Bir sonraki upstream güncellemesinde bu tablodaki uç SHA'larla yeni uçlar karşılaştırılır. Daha önce
ertelenen bir dal değişmediyse gerekçesi yeniden keşfedilmez; yalnız Respected'ın platform hedefi veya
dalın provider-neutral sözleşmesi değiştiyse karar yeniden açılır.

## 2026-08-29 tekrar kontrolü

| Kaynak | Güncel uç | Önceki incelemeye göre | Karar |
| --- | --- | --- | --- |
| `avenoxai/avenoxbeyin` `main` | `18c83ff` | Değişmedi | Yeni davranış yok. Actions v7 güncellemesi Respected Windows CI'ında zaten var. |
| `enesadakli/windows-native` | `920b597` | Değişmedi | Önceki karar korunuyor; ertelenen event log ve yedekleme ayrı özellikler. |
| `goktas-batuhan/fix/compile-trigger-reliability` | `5fed9f6` | Değişmedi | Compile güvenilirliği düzeltmeleri Respected'a daha önce uyarlandı. |
| `morp1e/windows-support` | `ac207ee` | Değişmedi | Native Windows davranışı Respected'ın ortak runtime'ında zaten karşılanıyor. |
| `eryondigital/fix/compile-stage-outside-dot-claude` | `065fb12` | Yeni incelendi | **Alınmalı ve provider-neutral biçimde uyarlanmalı.** |

Eryon düzeltmesi compile staging ağacını `.claude/scripts/.state` altından sistem geçici dizinine
taşıyor. Claude Code, headless `-p` çalışmasında `.claude/` altındaki yazmayı hassas sayıp onay
bekleyebildiği için model `0` koduyla fakat hiçbir dosya üretmeden çıkabiliyor. Respected'ın
`compile.py` dosyasında staging hâlâ aynı hassas konumda bulunduğundan hata bize de uygulanıyor.

Uyarlama 2026-08-31'de ayrı regresyon testiyle provider-neutral biçimde uygulandı: staging sistem
geçici dizinine taşındı; vault dışı sınır, `0700`, canlı `knowledge/` manifest/promote kontrolleri,
provider-neutral `model_runner.py` ve koşulsuz temizlik korundu.

## 2026-09-01 bütün forklar ve dallar incelemesi

İncelenen depoların yalnız varsayılan dalları değil bütün uzak dalları karşılaştırıldı. Ayrıntılı ve
kilitlenmiş uygulama kapsamı
[`UPSTREAM-ADOPTION-BACKLOG.md`](UPSTREAM-ADOPTION-BACKLOG.md) dosyasındadır.

| Kaynak | İncelenen dallar/uçlar | Sonuç |
| --- | --- | --- |
| `avenoxai/avenoxbeyin` | `main` `6f4dcb9`, `v2` `4a62dcc` | Referans taban; Respected'ta bulunan davranışlar tekrar alınmayacak. |
| `Ahmet53535353/avenoxbeyin` | `main` `612a14a`, `v2` `4a62dcc` | `f028135` pyenv/gerçek Python test fikri uyarlanacak. Eski lock düzeltmeleri ortak runtime tarafından aşılmış durumda. |
| `mehmetturuncx/avenoxbeyin` | `feat/google-antigravity-support` `4d6e90d`, `main` | Antigravity hedefi Respected'ta zaten tek lifecycle ile daha geniş karşılanıyor; kopya motor alınmayacak. |
| `banadabi/avenoxbeyin` | transcript `857351e`, pycache `f922558`, `main`, `v2` | Modern Codex normalize/retry ve tracked bytecode upgrade davranışları uyarlanacak. |
| `morp1e/avenoxbeyin` | `main` `888591b`, `windows-support` `ac207ee`, `v2` | `d39319d` unsafe-temp regresyonu eklenecek; Windows/staging üretim davranışı zaten mevcut. |
| `goktas-batuhan/avenoxbeyin` | compile reliability `5fed9f6`, `main`, `v2` | Compile trigger düzeltmeleri Respected'ta daha önce uyarlandı; yeni üretim kodu alınmayacak. |
| `enesadakli/avenoxbeyin` | `windows-native` `920b597`, `main`, `v2` | Immutable event log ve Restic yedekleme değerli bulundu; provider-neutral ve cross-platform yeniden tasarımla alınacak. |

### Güncellenen karar

Daha önce ertelenen immutable event log ve Restic/DPAPI yedekleme artık kapsam dışı değildir.
Kullanıcı onayıyla `1.3.0` yol haritasına alındılar; ancak fork kodları doğrudan cherry-pick
edilmeyecek. Event log, beş yazarın kullandığı doğrulanmış JSON kayıt + atomik projection modeliyle;
yedekleme ise opt-in, vault-dışı credential ve gerçek restore/hash doğrulamasıyla tasarlanacaktır.

Toplam yedi kabul edilmiş uyarlama şunlardır: modern Codex transcript'i, güvenli normalize + tek
şema retry'ı, tracked pycache temizliği, unsafe-temp ve pyenv regresyonları, transactional `1.3.0`
geçişi, immutable handoff event log ve doğrulanmış Restic yedekleme.

## 2026-09-02 bütün forklar ve dallar güncel kontrolü

Yedi repository GitHub'dan yeniden mirror klonlandı; yalnız varsayılan dallar değil bütün
`refs/heads/*` uçları ve ortak tabandan ayrılan commitler incelendi.

| Kaynak | Güncel dallar/uçlar | 2026-09-01'e göre sonuç |
| --- | --- | --- |
| `avenoxai/avenoxbeyin` | `main` `6f4dcb9`, `v2` `4a62dcc` | Değişmedi. |
| `Ahmet53535353/avenoxbeyin` | `main` `21df5e2`, Antigravity `406eff3`, `v2` `4a62dcc` | **Dört yeni main commit var; iki davranış fikri seçilerek alınmalı.** |
| `mehmetturuncx/avenoxbeyin` | Antigravity `4d6e90d`, `main` `6f4dcb9` | Değişmedi; ortak lifecycle/model runner mevcut davranışı karşılıyor. |
| `banadabi/avenoxbeyin` | transcript `857351e`, pycache `f922558`, `main`, `v2` | Değişmedi; backlog 1–3 geçerli. |
| `morp1e/avenoxbeyin` | `main` `888591b`, Windows `ac207ee`, `v2` | Değişmedi; unsafe-temp testi backlog 4'te. |
| `goktas-batuhan/avenoxbeyin` | compile `5fed9f6`, `main`, `v2` | Değişmedi; üretim düzeltmeleri daha önce uyarlandı. |
| `enesadakli/avenoxbeyin` | Windows/event log `920b597`, `main`, `v2` | Değişmedi; event log ve Restic backlog 6–7'de. |

### Ahmet `main` yeni commit analizi

| Commit | Davranış | Karar |
| --- | --- | --- |
| `ee61527` | Linux GitHub Actions workflow | **Fikri al.** Respected test setine ve salt-okunur workflow izinlerine uyarla. |
| `bfb76b4` | Linux temiz kurulum E2E testi | **Fikri al, kodu alma.** Test SETUP'ı elle tekrar ediyor, Claude stub'a ve hatalı `2.1.0` damgasına sabit. Canonical installer/render yollarıyla provider-neutral E2E yaz. |
| `5213c69` | Testte global `HOME=/dev/null` export'unu kaldırma | **Doğrudan alma.** Bir child shell export'u sonraki CI step'e sızmaz; bizim testler zaten subprocess başına geçici home kullanmalı. İzolasyon ilkesi E2E tasarımına alındı. |
| `21df5e2` | SessionEnd'den saatlik private Git push | **Fikri al, kodu alma.** Opt-in private Git snapshot publisher olarak yeniden tasarla. |

`21df5e2` doğrudan alınamaz: kullanıcı onayı olmadan etkinleşiyor, `pull` ile vault'u
değiştirebiliyor, bütün dosyaları `git add -A` ile stage ediyor, secret kapısı ve concurrency lock
kullanmıyor, push sonucunu doğrulamadan başarı zamanını yazıyor, hataları sessizce yutuyor ve Bash/
PowerShell lifecycle kodunu çoğaltıyor. Provider-neutral uyarlama ortak worker, preview/apply,
divergence fail-closed, staged manifest/secret kontrolü, uzak commit doğrulaması ve yalnız başarıdan
sonra atomik receipt gerektirir.

Sonuç olarak önceki yedi madde korunmuş, iki yeni aday eklenmiştir: opt-in private Git snapshot
publisher ve Linux CI + provider-neutral fresh-install E2E. Yeniden adlandırma `1.3.0` ayrı
migration sürümü olduğundan dokuz maddelik upstream kapsamı `1.4.0` olarak planlanır.
