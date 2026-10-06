# 💾 Yedekleme ve Geri Dönüş

> Not yedeği, program kurulumunun transaction yedeği ve geliştirici kanıt arşivi üç farklı şeydir.

## 1. Neyi yedekliyorum?

| Alan | Neden gerekir? |
| --- | --- |
| Tam VaultRoot | İnsan notları, daily, knowledge, Companion, Templates, `.obsidian`, taşınabilir marker |
| DataRoot | Ayarlar, kayıtlı kasa yolları, overrides, teknik state ve işlem yedekleri |
| AppRoot/native paket | Programı aynı sürümle yeniden kurma; not yedeği değildir |
| Kaynak repo `.local/archives/` | Yerel geliştirme/test kanıtı; kişisel kasa yedeği değildir |

Program transaction yedeği yalnız o işlemde değişen dosyaları kapsar; tüm kasanın düzenli yedeği gibi düşünülmez. Cache yeniden üretilebilir olsa da session/idempotency state tekrar önleme görevi taşır; hepsi rastgele silinmez.

## 2. Eski kasayı ZIP'leyip yeni kasa açma

1. Notları/CLI işlerini yazan süreçlerin tamamlandığından emin olun.
2. Kasayı gizli dosyalar dahil ayrı ZIP/arşive alın; yedek hedefini kasa içine koymayın.
3. Arşivi ayrı geçici konuma açıp dosya listesi, boyut ve mümkünse SHA256 karşılaştırın.
4. Doğrulanmış arşivi koruyun; yeni boş kasa ayrı yol ve yeni UUID ile başlasın.

Bu rehber eski kasayı silme komutu değildir. Kimlik aynı kaldığında iki kopyayı bağımsız aktif kasa diye kaydetmek UUID conflict'i yaratabilir. [Kasa seçimi](CONFIGURATION.md), [devreye alma sınırları](../PROJECT_STATUS.md).

## 3. Restic yardımcısı

Harici `restic` executable ve repository erişimi gerekir. Preview:

```text
respectedbrain maintenance --vault-id <UUID> backup_restic --repo "<restic repository>"
```

Uygulamak için aynı komuta `--apply` eklenir. Varsayılan restore verification, Restic restore'un başarılı tamamlanmasını sınar; her notun semantik doğruluğunu veya bağımsız dosya-hash karşılaştırmasını garanti etmez. `--skip-verify` doğrulamayı kapatır. Repository/password gibi credentials kaynak repoya veya açık notlara konmaz. Kesin seçenekler [CLI](../development/CLI.md).

## 4. Git snapshot yayını

```text
respectedbrain maintenance --vault-id <UUID> publish_git_snapshot
```

Varsayılan preview'dir; dal kontrolü için fetch yapabilir. `--apply` gerçek commit/push işidir ve veri dışarı gönderir. Private repo olması notların içinde secret olmadığı anlamına gelmez. Mevcut guard dosya adı kalıplarını sınar; önceden tracked dosyalar ve not gövdesindeki sırları eksiksiz taramaz. [Güvenlik sınırları](../SECURITY.md) ve tarihli denetim [kayıt denetiminde](../records/2026-10-installer-release/REPOSITORY_AUDIT.md).

## SSS

**Yedek klasörünü silsem program çalışır mı?** Çalışabilmesi, geri dönüş kanıtının gereksiz olduğu anlamına gelmez. Yedek silme kararı restore/hash doğrulaması ve tutulması gereken geçmişle birlikte verilir.

**Yeni kurulum notlarımı geri yükler mi?** Hayır. Yeni kasa template başlangıcıdır. Restore ayrı işlemdir; kurucu eski notları otomatik kopyalamış sayılmaz.
