# FINDINGS-A

> Tarihsel test geliştirme kaydıdır. Güncel mimari sözleşmesi `docs/SPEC-V2.md` dosyasındadır.

## BLOCKER 2: `--no-git` vault yedeği, çözüldü

**Durum:** YEŞİL
**Regresyon testleri:** `tests/upgrade_transaction_test.sh`, vaka 12 ve 13

### İlk bulgu

Lane brifingi vaka 12'yi "`--no-git` vault'ta apply, `BEYIN_BACKUP_ROOT` altında
doğrulanmış bir kopya bırakmalı" diye yazıyordu. Test bu haliyle kırmızıydı:
`git` ikilisi makinede varsa `apply`, vault'ta `.git` olmasa bile `git init`
çalıştırıyor, `SNAP_OK=1` oluyor ve harici kopya dalı hiç çalışmıyor.

### Neden gereksinim yeniden yazıldı

Asıl gereksinim "harici kopya" değil, "geri dönülebilir doğrulanmış bir nokta
bırakmadan ilerleme". `git init` artı anlık görüntü commit'i bunu zaten
karşılıyor ve dosya kopyasından daha iyi karşılıyor: tam ağaç, sürümlü, geri
alınabilir. Brifingdeki "kopya" ifadesi bir uygulama ayrıntısını gereksinim
sanmıştı.

Harici kopya dalının gerçek işi ayrı: makinede `git` ikilisi hiç yoksa devreye
giriyor. Asıl kapsanmayan yol buydu.

### Şimdiki kapsama

- **Vaka 12** gereksinimin kendisini doğruluyor: `--no-git` vault'ta `apply`,
  doğrulanmış bir anlık görüntü bırakmadan ilerlemiyor.
- **Vaka 13** harici dalı `git` ikilisini PATH'ten gizleyerek gerçekten
  çalıştırıyor: `BEYIN_BACKUP_ROOT` altında kopya oluşuyor ve öğe sayısı
  kaynakla birebir eşleşiyor.

`scripts/upgrade.sh` bu bulgu nedeniyle değiştirilmedi.

### Doğrulama

```bash
bash tests/upgrade_transaction_test.sh
```

Son koşu: **16/16 geçti**.
