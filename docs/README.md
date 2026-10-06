# 📚 Respected Brain — Belge Merkezi

> Bu klasör programı kullanmak, geliştirmek ve doğrulama kanıtını anlamak içindir. Her belgenin tek bir görevi vardır; ayrıntılı dosya envanteri yalnız [depo atlasında](REPOSITORY_MAP.md) tutulur.

## 1. Nereden başlamalıyım?

| İhtiyaç | Okuma sırası |
| --- | --- |
| Programı tanımak | [Ana README](../README.md) → [Mimari](ARCHITECTURE.md) |
| Kurmak ve ilk konuşmayı yapmak | [Kurulum](guides/SETUP.md) → [Windows](guides/SETUP-WINDOWS.md) / [macOS-Linux](guides/SETUP-POSIX.md) → [İlk çalıştırma](guides/BOOTSTRAP.md) |
| Günlük kullanmak | [Günlük kullanım](guides/DAILY_USE.md) → [Çoklu AI](guides/MULTI_AI.md) |
| Ayar/kasa değiştirmek | [Yapılandırma](guides/CONFIGURATION.md) |
| Bakım yapmak | [Yedekleme](guides/BACKUP.md), [Güncelleme](guides/UPDATE.md), [Kaldırma](guides/UNINSTALL.md), [Sorun giderme](guides/TROUBLESHOOTING.md) |
| Kod geliştirmek | [Geliştirici rehberi](development/README.md) → [Komut kataloğu](development/CLI.md) → [Dosya atlası](REPOSITORY_MAP.md) |
| Hangi garanti uygulanıyor? | [Davranış sözleşmesi](SPECIFICATION.md) → [Güvenlik sınırları](SECURITY.md) |
| Ne test edildi / ne kaldı? | [Proje durumu](PROJECT_STATUS.md) → [Test matrisi](TEST-MATRIX.md) → [Tarihli denetim](records/2026-10-installer-release/REPOSITORY_AUDIT.md) |

## 2. Belge türleri

```text
docs/
├── README.md                   Bu giriş ve okuma rotaları
├── ARCHITECTURE.md             Güncel kaynak/kurulum/veri düzeni
├── SPECIFICATION.md            Davranış kuralları ve kabul sınırları
├── PROJECT_STATUS.md           Tek aktif ürün durumu ve kalan işler
├── SECURITY.md                 Uygulanan korumalar ve açık sınırlar
├── TEST-MATRIX.md              Tarihli kanıt ve kapsam ayrımı
├── REPOSITORY_MAP.md           Otomatik üretilen eksiksiz atlas
├── repository_inventory.json  Atlasın incelenmiş açıklama kaynağı
├── guides/                     Son kullanıcı rehberleri
├── development/                CLI ve geliştirici/kalite akışı
├── decisions/                  Kullanıcının onayladığı tasarım kayıtları
└── records/                    Tarihli uygulama ve doğrulama kayıtları
```

`decisions/` neye karar verildiğini, `records/` o tarihte ne yapılıp sınandığını açıklar. Kayıtlardaki eski test sayısı veya “bekleniyor” ifadesi bugünkü iş listesi değildir. Eski 2026-09 ürün ve kurulum metinleri yerel arşiv yedeklerinde korunur, kaynak ağacından sadeleştirilerek kaldırılmıştır.

## 3. Doğru bilgi nasıl korunur?

- Aktif ürün durumu yalnız PROJECT_STATUS içinde tutulur. Bu bilgisayara özel devreye alma tercihi Git dışındaki `.local/ROLLOUT.md` kaydındadır; başka makinelerde bu yerel dosyanın bulunması beklenmez. Onaylı tasarım `decisions/` altındadır.
- Ürün davranışı kaynak kod/testle, test sonucu tarih/commit/koşu ile anlatılır. Hedef, uygulanmış özellik ve doğrulanmış sonuç birbirinin yerine kullanılmaz.
- Code değişince ilgili rehber aynı görevde gözden geçirilir. Dosya ekleme/silme/taşıma ve sorumluluk değişikliğinde JSON envanteri incelenir; atlas yeniden üretilir.
- Eksik/fazla/çift kayıt, eski inceleme hash'i veya atlas üretim farkı `python tools/repository_map.py --check` ile reddedilir. Araç açıklamaların doğru olduğunu kendisi anlayamaz.
- Tarihli kayıtlar geçmiş sonuçları güncele çevirecek şekilde yeniden yazılmaz. Yeni sonuç yeni tarihli kayıttır. Uzun kayıtlar bilgi budanmadan bölünür; tek dosya atlası bilinçli istisnadır.

## SSS

**Bütün belgeleri okumalı mıyım?** Hayır. Yukarıdaki ihtiyacınıza uygun rotayı izleyin. Kullanıcının kurulum yapmak için uygulama planlarını okuması gerekmez.

**Atlas ve JSON neden ikisi de var?** JSON düzenlenebilir rol/amaç/ilişki kaynağıdır; Markdown aynı kaynağın okunabilir çıktısıdır. Atlas elle düzenlenmez.

**Yerel yedekler burada mı?** Kaynak dışı geliştirme kanıtları `.local/archives/` içinde Git'ten hariçtir; içerikleri [belge düzenleme kaydında](records/2026-10-documentation/REORGANIZATION.md) açıklanır. Kişisel not kasasının yedeği ayrı konudur.
