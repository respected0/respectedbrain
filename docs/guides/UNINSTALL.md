# 🗑️ Programı Kaldırma

> Programın kaldırılması not kasasının silinmesi değildir. Sahiplik kuralları [SPECIFICATION](../SPECIFICATION.md), yedekleme [BACKUP](BACKUP.md).

## 1. Neler kaldırılır, neler korunur?

| Alan | Davranış |
| --- | --- |
| AppRoot sahipli program dosyaları | Manifest/hash kanıtıyla kaldırılır |
| Sahipli global/MCP/scheduler/shortcut kayıtları | External kayıt sahipliği/aynı değer kontrolüyle temizlenir |
| Yeni kasaya kurulumun eklediği yerel AI hook dosyaları | External sahiplik manifestiyle temizlenir; global entegrasyon tercihi kapalıyken de sahiplik korunur. Değiştirilmiş dosya korunur ve conflict bildirilir |
| Bağımsız kullanıcı dosyası veya değiştirilmiş sahipli dosya | Otomatik silinmez; conflict raporlanabilir |
| VaultRoot notlar, daily, knowledge, `.obsidian` | Uninstall/purge-data hedefi değildir |
| DataRoot teknik kayıt/ayar/yedekler | Varsayılan olarak kanıtlı sahipli teknik kayıtlar (config, manifest) temizlenir; audit, yedekler ve bilinmeyen kullanıcı dosyaları korunur. `--keep-data` teknik temizliği atlar |

## 2. Kaldırma yolları

Windows kurulumunda Program Ekle/Kaldır kaydı veya ortak CLI kullanılabilir:

```text
respectedbrain uninstall --vault-id <UUID>
```

Windows'ta çalışan frozen exe kaldırma işini exit sonrası helper'a devredebilir. `pending` sonucu receipt/son health sonucu olmadan bitmiş sayılmaz. Değişmiş dosya conflict'i varsa klasörü elle komple silmek ürünün sahiplik korumasını baypas eder.

## 3. Teknik veri temizliği (varsayılan) ve --keep-data

```text
respectedbrain uninstall --vault-id <UUID>            # varsayılan: kanıtlı teknik kayıtlar temizlenir
respectedbrain uninstall --vault-id <UUID> --keep-data
```

Varsayılan kaldırma yalnız kanıtlı sahipli teknik kayıtları (config, install-manifest gibi) temizler; audit günlükleri, yedekler ve bilinmeyen kullanıcı dosyaları korunur ve kasa hiçbir zaman silinmez. `--keep-data` teknik veri temizliğini tamamen atlar; açık `--purge-data` yazmak da aynı varsayılan kapsamı uygular. Eski arşivlerdeki `--purge-vault` mevcut CLI seçeneği değildir.

## 4. Kaldırma sonrası kontrol

Sahipli OS görev/bağlantıların ve kasa içindeki uygulamaya bağlı hook dosyalarının kaldırıldığını, bağımsız notify zincirinin ve notların korunduğunu kontrol edin. Yerel hook dosyasını değiştirdiyseniz kaldırıcı dosyayı koruyup conflict bildirir; ayarınızı gözden geçirerek kalan uygulama bağlantısını ayırın. Byte hash veya yedek karşılaştırması dosya varlığından daha güçlü kanıttır. Recovery conflict'ini aşmak için eski geniş silme yapan kaldırıcı çalıştırmayın. Sorun varsa işlem kimliği/receipt/log ile [TROUBLESHOOTING](TROUBLESHOOTING.md).
