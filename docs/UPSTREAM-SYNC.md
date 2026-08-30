# Upstream senkronizasyon kaydı

Bu dosya Respot Brain'in `avenoxai/avenoxbeyin` ve ilgili fork değişikliklerini nasıl
değerlendirdiğini kaydeder. Amaç kör merge değil; doğrulanmış davranışı provider-neutral Respot
katmanına uyarlamak ve sonraki incelemede aynı analizi tekrarlamamaktır.

## Politika

1. Önce `./scripts/upstream_sync.sh check` ile yeni upstream commitleri listelenir.
2. Her commit davranış ve test düzeyinde incelenir; yalnız dosya benzerliğine bakılmaz.
3. Claude-only kod, Respot'ın Claude/Codex/Cursor/Antigravity model seçimini geriletemez.
4. Güvenlik, kullanıcı hafızasını koruma, WSL köprüsü ve tek-kaynak adapter üretimi korunur.
5. Alınan davranış için önce başarısız regresyon testi yazılır; tam test kapısı geçmeden yayınlanmaz.
6. Büyük platform veya yedekleme mimarileri çekirdek bug fixi gibi cherry-pick edilmez; ayrı tasarım
   ve platform doğrulaması ister.

## 2026-08-28 incelemesi

| Kaynak | İncelenen uç | Karar | Gerekçe |
| --- | --- | --- | --- |
| `avenoxai/avenoxbeyin` `main` | `18c83ff` | Seçerek uyarla | Göktaş compile düzeltmeleri ve Morp1e Windows portu upstream'e girmiş durumda. |
| `goktas-batuhan/fix/compile-trigger-reliability` | `2331ee2`, `5fed9f6` | **Alındı ve uyarlandı** | Başarılı trigger claim sızıntısı, kaçırılan akşam derlemesi ve kısmi bugünün erken ingest edilmesi gerçek platform-bağımsız hatalardı. Respot'ın `_run_model` ve Antigravity transkript desteği korunarak taşındı. |
| `morp1e/windows-support` | `ac207ee` | **Davranış seçilerek alındı** | PowerShell preflight, native lock/process ihtiyaçları ve Windows CI dersleri provider-neutral kurucuya uyarlandı. Claude zorunluluğu, `_run_claude` ve ayrı PowerShell lifecycle kopyaları alınmadı. |
| `enesadakli/windows-native` | `920b597` | **Temel parçalar alındı** | Native Python lifecycle, reparse-point güvenliği ve installer test yaklaşımı tek ortak runtime'a uyarlandı. Immutable event log, genişletilmiş doctor ve Restic/DPAPI yedekleme ayrı projeler olarak ertelendi. |

### Bu turda alınan davranış

- SessionEnd sonrası başarılı compile, `compile-trigger-YYYY-MM-DD` claim'ini mutlaka bırakır.
- SessionStart bağlam çıktısından sonra ayrık `--maybe-compile` catch-up çağrısı yapar.
- Catch-up yalnız tamamlanmış önceki günleri seçer; bugünün daily dosyası `--before-date` ile dışarıda
  kalır. Bu sınır SessionStart saat 18:00'den sonra açılsa bile korunur; upstream patchindeki saat
  koşulu Respot'ta bu köşe durumuna göre sıkılaştırıldı.
- Saat 18:00 sonrası normal SessionEnd davranışı değişmez.
- Model çalıştırma hâlâ provider-neutral `model_runner.py` üzerinden yapılır.

### Provider-neutral native Windows temeli

`5cc4c36` commit'iyle forkların yararlı Windows davranışı Respot mimarisine uyarlandı:

- Claude/Codex/Cursor/Antigravity için tek `lifecycle.py`; POSIX hook'lar yalnız ince launcher;
- POSIX `fcntl` ve Windows `msvcrt` kullanan ortak kilit, detached process ve path containment API'si;
- `portable`, `windows-wsl`, `windows-native` olmak üzere üç deterministik profil;
- `py.exe -3` ve mutlak Windows bridge yolu kullanan proje/global adaptörleri;
- Claude gerektirmeyen PowerShell 5.1 uyumlu taze kurucu ve `1.0.0 → 1.1.0` transactional updater;
- gerçek Windows PowerShell kurulum testi ve Windows Python süreçlerinde dört provider lifecycle,
  concurrency, detached flush, quota fallback ve current-day catch-up sınırı;
- `.github/workflows/windows.yml` içindeki `windows-latest` release kapısı. Commit `5855918` için
  [windows-native #33209497580](https://github.com/respected0/respot-brain/actions/runs/33209497580)
  42 saniyede geçti; PowerShell fresh-install ve native lifecycle/runtime adımları yeşil.

### Bilinçli olarak alınmayanlar

- Upstream PowerShell hook dosyaları ve Claude-only Windows installer doğrudan kopyalanmadı; aynı
  ihtiyaç tek Python lifecycle ve provider seçmeli Respot kurucusuyla karşılandı.
- Enes dalındaki Restic/DPAPI yedekleme otomatik etkinleştirilmedi.
- Immutable bridge event log ve git-geçmişine dayalı doctor kontrolleri bu bug-fix turuna eklenmedi.
- Damgasız v1 vault'un native Windows migrasyonu açılmadı; doğrulanmış WSL transaction korunuyor.

## Sonraki inceleme

Bir sonraki upstream güncellemesinde bu tablodaki uç SHA'larla yeni uçlar karşılaştırılır. Daha önce
ertelenen bir dal değişmediyse gerekçesi yeniden keşfedilmez; yalnız Respot'ın platform hedefi veya
dalın provider-neutral sözleşmesi değiştiyse karar yeniden açılır.

## 2026-08-29 tekrar kontrolü

| Kaynak | Güncel uç | Önceki incelemeye göre | Karar |
| --- | --- | --- | --- |
| `avenoxai/avenoxbeyin` `main` | `18c83ff` | Değişmedi | Yeni davranış yok. Actions v7 güncellemesi Respot Windows CI'ında zaten var. |
| `enesadakli/windows-native` | `920b597` | Değişmedi | Önceki karar korunuyor; ertelenen event log ve yedekleme ayrı özellikler. |
| `goktas-batuhan/fix/compile-trigger-reliability` | `5fed9f6` | Değişmedi | Compile güvenilirliği düzeltmeleri Respot'a daha önce uyarlandı. |
| `morp1e/windows-support` | `ac207ee` | Değişmedi | Native Windows davranışı Respot'ın ortak runtime'ında zaten karşılanıyor. |
| `eryondigital/fix/compile-stage-outside-dot-claude` | `065fb12` | Yeni incelendi | **Alınmalı ve provider-neutral biçimde uyarlanmalı.** |

Eryon düzeltmesi compile staging ağacını `.claude/scripts/.state` altından sistem geçici dizinine
taşıyor. Claude Code, headless `-p` çalışmasında `.claude/` altındaki yazmayı hassas sayıp onay
bekleyebildiği için model `0` koduyla fakat hiçbir dosya üretmeden çıkabiliyor. Respot'ın
`compile.py` dosyasında staging hâlâ aynı hassas konumda bulunduğundan hata bize de uygulanıyor.

Uyarlamada rastgele ve `0700` izinli geçici klasör, her koşulda temizlik, canlı `knowledge/`
sınırlarının yeniden doğrulanması ve provider-neutral `model_runner.py` korunacak. Bu değişiklik
özellik backlog'u kesinleştiğinde ayrı regresyon testiyle uygulanacak; bu inceleme turunda çalışma
kodu değiştirilmedi.
