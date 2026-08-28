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
| `morp1e/windows-support` | `ac207ee` | Ayrı Windows-native tasarımına ertelendi | Temiz kurulum için native PowerShell desteği değerli; fakat mevcut hali Claude CLI zorunlu, `_run_claude` kullanıyor ve Respot'ın dört-agent fallback/transkript sözleşmesini geriletiyor. WSL yolu etkilenmedi. |
| `enesadakli/windows-native` | `920b597` | Parçalara ayrılarak ertelendi | Native Python hook/doctor, immutable bridge log ve Restic yedekleme yaklaşık 6.000 satırlık alternatif mimari. Claude/Codex ağırlıklı; backup ve event log çekirdek compile düzeltmesinden bağımsız kararlar. |

### Bu turda alınan davranış

- SessionEnd sonrası başarılı compile, `compile-trigger-YYYY-MM-DD` claim'ini mutlaka bırakır.
- SessionStart bağlam çıktısından sonra ayrık `--maybe-compile` catch-up çağrısı yapar.
- Catch-up yalnız tamamlanmış önceki günleri seçer; bugünün daily dosyası `--before-date` ile dışarıda
  kalır. Bu sınır SessionStart saat 18:00'den sonra açılsa bile korunur; upstream patchindeki saat
  koşulu Respot'ta bu köşe durumuna göre sıkılaştırıldı.
- Saat 18:00 sonrası normal SessionEnd davranışı değişmez.
- Model çalıştırma hâlâ provider-neutral `model_runner.py` üzerinden yapılır.

### Bilinçli olarak alınmayanlar

- Upstream PowerShell hook dosyaları ve Claude-only Windows installer doğrudan kopyalanmadı.
- Enes dalındaki Restic/DPAPI yedekleme otomatik etkinleştirilmedi.
- Immutable bridge event log ve git-geçmişine dayalı doctor kontrolleri bu bug-fix turuna eklenmedi.
- Upstream Windows GitHub Actions işi, Respot'ta eşdeğer native Windows çalışma profili bulunmadan
  eklenmedi.

## Sonraki inceleme

Bir sonraki upstream güncellemesinde bu tablodaki uç SHA'larla yeni uçlar karşılaştırılır. Daha önce
ertelenen bir dal değişmediyse gerekçesi yeniden keşfedilmez; yalnız Respot'ın platform hedefi veya
dalın provider-neutral sözleşmesi değiştiyse karar yeniden açılır.
