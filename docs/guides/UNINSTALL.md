# 🗑️ Programı Kaldırma

> Programın kaldırılması not kasasının silinmesi değildir. Sahiplik kuralları [SPECIFICATION](../SPECIFICATION.md), yedekleme [BACKUP](BACKUP.md).

## 1. Neler kaldırılır, neler korunur?

| Alan | Davranış |
| --- | --- |
| AppRoot sahipli program dosyaları | Manifest/hash kanıtıyla kaldırılır |
| Sahipli global/MCP/scheduler/shortcut kayıtları | External kayıt sahipliği/aynı değer kontrolüyle temizlenir |
| Bağımsız kullanıcı dosyası veya değiştirilmiş sahipli dosya | Otomatik silinmez; conflict raporlanabilir |
| VaultRoot notlar, daily, knowledge, `.obsidian` | Uninstall/purge-data hedefi değildir |
| DataRoot teknik kayıt/ayar/yedekler | Varsayılan korunur; açık purge-data ayrı sınırdır |

## 2. Kaldırma yolları

Windows kurulumunda Program Ekle/Kaldır kaydı veya ortak CLI kullanılabilir:

```text
respectedbrain uninstall --vault-id <UUID>
```

Windows'ta çalışan frozen exe kaldırma işini exit sonrası helper'a devredebilir. `pending` sonucu receipt/son health sonucu olmadan bitmiş sayılmaz. Değişmiş dosya conflict'i varsa klasörü elle komple silmek ürünün sahiplik korumasını baypas eder.

## 3. purge-data tam olarak ne?

```text
respectedbrain uninstall --vault-id <UUID> --purge-data
```

Bu açık bayrak yalnız kanıtlı sahipli teknik veriyi temizleme kapsamı ekler. Kasayı silmez; bilinmeyen kullanıcı dosyasını teknik alan içinde diye otomatik owned saymaz. Eski arşivlerdeki `--purge-vault` mevcut CLI seçeneği değildir.

## 4. Kaldırma sonrası kontrol

Sahipli OS görev/bağlantıların kaldırıldığını, bağımsız notify zincirinin ve notların korunduğunu kontrol edin. Byte hash veya yedek karşılaştırması dosya varlığından daha güçlü kanıttır. Recovery conflict'ini aşmak için eski geniş silme yapan kaldırıcı çalıştırmayın. Sorun varsa işlem kimliği/receipt/log ile [TROUBLESHOOTING](TROUBLESHOOTING.md).
