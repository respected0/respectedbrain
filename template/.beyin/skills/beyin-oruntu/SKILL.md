---
name: beyin-oruntu
description: Son 30 gündeki örtük sürtünme ve darboğaz örüntülerini çıkarır. "örüntü", "trend", "nerede takılıyoruz" dendiğinde kullan.
---

# Beyin Örüntü Çıkarıcı (/emerge)

## Amaç ve İlke

Furkan birden fazla projede yoğun çalışırken aynı hatayı farklı isimlerle tekrar tekrar çözebilir veya bazı konular sürekli tıkanıyor olabilir. Bu beceri, son 30 günün loglarını (`daily/`) ve açık konuları (`Threads.md`) derinlemesine tarayarak kullanıcının adını koymadığı gizli paternleri su yüzüne çıkarır.

## Akış

1. **Zaman Penceresini Belirle:**
   Varsayılan olarak son 30 günün `daily/` kayıtlarını ve `🔮 850-Companion/Threads.md` dosyasını tara. Kullanıcı özel bir aralık verdiyse ona göre daralt.

2. **Kesişim Noktalarını ve Tekrarları Bul:**
   - **Tekrarlayan Engeller:** Hangi hata mesajları, kütüphane çakışmaları veya ortam sorunları birden fazla oturumda tekrar yaşandı?
   - **Ertelenen Kararlar:** Hangi görevler veya açık başlıklar sürekli "yarın yapılacak" diyerek günlerce sürüklendi?
   - **Yakınsayan İhtiyaçlar:** Farklı projelerde ayrı ayrı geliştirilen ancak aslında tek bir ortak kütüphane veya kural olabilecek yapılar var mı?

3. **Örüntü Raporunu Üret:**
   Aşağıdaki 3 ana başlıkta net bir sentez sun:
   - **1. Gizli Sürtünme Noktaları (Hidden Friction):** Nerede açıklanamayan zaman/enerji kaybı var?
   - **2. Ortak Çözüm Fırsatları (Convergence):** Hangi parçalar birleştirilmeli?
   - **3. Kural Adayları (Rule Candidates):** `Kurallar.md` içine kural olarak yazılması tavsiye edilen 1-2 somut madde.

4. **Kullanıcı Onayı:**
   Kullanıcı kural adaylarından birini onaylarsa, kuralı doğrudan `🔮 850-Companion/Kurallar.md` dosyasına işle.
