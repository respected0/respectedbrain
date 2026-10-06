# 🗂️ Tarihli Çalışma ve Doğrulama Kayıtları

Bu bölüm geçmişte ne kararlaştırıldığını, ne uygulandığını ve hangi kapsamın doğrulandığını açıklar. Tarihli kayıtları bugünün yapılacaklar listesi olarak kullanmayın. Aktif işlerin tek kaynağı [PROJECT_STATUS](../PROJECT_STATUS.md), güncel test kapsamının giriş noktası [TEST-MATRIX](../TEST-MATRIX.md) olur.

## 1. Kayıt grupları

| Dönem / konu | Belgeler | Nasıl okunmalı? |
| --- | --- | --- |
| Önceki ürün yapısı (2026-09) | `.local/archives/` yerel yedeğinde | Önceki yapı referansı; kaynak ağacından sadeleştirilerek kaldırıldı |
| Modüler temel (2026-10) | [Uygulama](2026-10-modular-foundation/IMPLEMENTATION.md), [Doğrulama](2026-10-modular-foundation/VERIFICATION.md) | Tek paket ve modüler yapının 14 görevinin sözleşmeleri ve kabul kanıtı |
| Kaynak temizliği (2026-10) | [Doğrulama ve yürütme](2026-10-source-cleanup/VERIFICATION.md), [Modül inceleme kaydı](2026-10-source-cleanup/SOURCE_REVIEW.md) | Eski geçiş katmanının kaldırılması ve sonraki modül incelemesinin fixture kanıtları |
| Kurucu / atlas / yayın hazırlığı | [Yürütme](2026-10-installer-release/EXECUTION.md), [Depo denetimi](2026-10-installer-release/REPOSITORY_AUDIT.md) | Seçenek aktarımı, atlas üretimi ve 12/12 CI platform kanıtının tarihçesi |
| Belge düzenleme (2026-10) | [Yeniden düzenleme kaydı](2026-10-documentation/REORGANIZATION.md) | Belge mimarisinin sadeleştirilmesi, atlas bakımı ve doğrulama sonuçları |

Tarihli eski belgeler (2026-09-legacy metinleri ve ilk inceleme taslakları) hash kontrollü yerel arşivde saklanır. Aktif belgeler doğrudan güncel kod ve sözleşmelere bağlanır. Bütün dosyalar [dosya atlasında](../REPOSITORY_MAP.md) ayrı ayrı açıklanır.

## 2. Kanıt nasıl yorumlanır?

Commit veya CI kimliği varsa yalnız o kaynağa ait kanıtı ifade eder. Bir yerel Windows kaydı Linux/macOS/WSL doğrulaması yerine geçmez. Geçmişteki açık maddeler daha sonra kapanmış olabilir; güncel karar için aktif duruma, davranış için kod ve güncel rehbere bakın.

Tarihsel komutlar eski yollar veya artık var olmayan araçlar içerebilir. Bağlantı uyarlaması ve süreç talimatlarının kaldırılması kaydın girişinde belirtilmiştir. Ham başlangıç metni yerel ZIP yedeğinde korunur; bu uyarlamalar geçmiş ürün davranışını değiştirmez.
