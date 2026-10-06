# 🔄 Güncelleme, Onarım ve Eski Kurulum

> Paket güncellemesi program dosyalarını değiştirir; notların yerini ve kimliğini korur. Önce [yedekleme](BACKUP.md), sözleşme için [SPECIFICATION](../SPECIFICATION.md).

## 1. Güncel native programı güncelleme

```text
respectedbrain update --vault-id <UUID> --package "<yeni doğrulanmış native dağıtım>"
```

Paket doğru OS için `distribution.json` ve hash'lerle doğrulanır. Kaynak `src/`, wheel dosyası veya rastgele klasör native dağıtım yerine geçmez. Program sahipliği ve değişmemiş hash kontrolü kullanılır; notlar, `.obsidian`, Templates ve kişisel override alanları fresh template ile yeniden yazılmaz.

Windows frozen launcher kendisini değiştirmek için exit sonrası helper'a işi devredebilir. Çıktıda `pending` varsa receipt yolunu kontrol edin; process exit 0 son kurulumun bittiğini tek başına göstermez. OperationResult alanları `success`, `pending`, `tx_id`, `conflicts` olur; ayrı bir receipt alanı yoktur. Deferred makbuz yolu DataRoot altında `backups/<tx_id>/result.json` olarak çözülür; [Windows rehberi](SETUP-WINDOWS.md).

## 2. Onarım ve recovery

```text
respectedbrain repair --vault-id <UUID>
respectedbrain recover
```

Repair sahipli uygulama/desired bağlantıları onarır; kişisel hafıza reset'i değildir. Recover DataRoot'taki yarım transaction'ları inceler. Journal/byte yedeği ve compare-and-swap ile geri alma yapılır; kullanıcının işlemden sonra değiştirdiği dosya zorla eski haline getirilmez. Conflicts varsa log/backup kimliğini koruyup [sorun giderme](TROUBLESHOOTING.md) akışını izleyin.

## 3. Eski layout: önce salt okunur migration planı

```text
respectedbrain migrate --legacy-root "<eski program kökü>" --vault "<mevcut eski kasa>"
```

Bu plan source/target/action/hash/ownership, korunacak dosyalar ve conflict'leri gösterir. Varsayılan dry-run (önizleme) config/state/log/backup yazmaz; geçişi uygulamak için ayrıca `--apply` gerekir. İsim, `.py` uzantısı veya klasör konumu sahiplik kanıtı değildir. Farklı state kopyaları, aktif yazıcı veya path/reparse kaçışı conflict üretir; force ile geçilmez.

Somut plan ve doğrulanmış paketle:

```text
respectedbrain migrate --legacy-root "<eski program kökü>" --vault "<mevcut eski kasa>" --package "<yeni native dağıtım>" --apply
```

Apply mutasyon yapar; source/target/external hash'ler kilit sonrası tekrar doğrulanır, yedekler/journal yazılır. Eski geniş temizlik yapan uninstaller çalıştırılmaz. Yalnız unchanged owned artıklara cleanup uygulanır, bilinmeyen kullanıcı dosyası kalır. Cache yeniden üretilebilir; idempotency state sıradan cache gibi silinmez.

## 4. Yeni boş kasa seçiyorsanız

Eski kasayı aktarmak zorunlu değildir. Eski kasanın doğrulanmış yedeğini ayrı tutup yeni boş kasayı [SETUP](SETUP.md) ile kurabilirsiniz. Eski AppRoot/DataRoot ve global notify/MCP/scheduler kayıtları yine ayrı ele alınır; eski kasayı ZIP'lemek bunları otomatik temizlemez. Genel devreye alma sınırları [PROJECT_STATUS](../PROJECT_STATUS.md) içindedir; bu bilgisayara özel tercih Git dışındaki `.local/ROLLOUT.md` kaydındadır.

**Süre ne kadar?** Paket/disk/OS/antivirüs etkiler. Tarihsel profilli hız ölçümü gerçek kullanıcı kurulumu için sabit süre vaadi değildir; [test kanıtı](../TEST-MATRIX.md).
