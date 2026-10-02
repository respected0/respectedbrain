# AI Software Development Quality Rules (Kısım 1: Madde 1-13)

Bu projede yalnızca çalışan kod üretmek yeterli değildir. Her geliştirme görevinde kalite, hata toleransı, regresyon güvenliği ve gerçek dünya senaryoları dikkate alınmalıdır.

## 1. Kendi Kodunu Doğru Varsayma

Yazdığın veya değiştirdiğin kodu otomatik olarak doğru kabul etme.

Implementasyon tamamlandıktan sonra zihinsel olarak rol değiştir:

* Önce geliştirici gibi implement et.
* Ardından bağımsız bir senior reviewer / QA engineer gibi incele.
* Kendi implementasyonunu doğrulamaya değil, bozabilecek durumları bulmaya çalış.

Şu soruyu temel al:

> "Bu kod çalışıyor mu?" yerine "Bu kod hangi koşullarda bozulabilir?"

---

## 2. Sadece Happy Path Test Etme

Her önemli özellik için normal kullanım senaryosunun yanında hata ve edge-case senaryolarını da değerlendir.

Uygun olduğu durumlarda özellikle kontrol et:

* null / undefined / empty değerler
* geçersiz input
* sınır değerler
* duplicate işlemler
* kullanıcı işlemi çok hızlı tekrar ederse
* yanlış işlem sırası
* API timeout
* network kesilmesi
* API 4xx / 5xx cevapları
* partial failure
* retry davranışı
* uygulamanın veya işlemin yarıda kapanması
* stale state
* cache problemleri
* race condition
* concurrency
* aynı işlemin iki kez tetiklenmesi
* auth/session expiration
* permission sorunları
* beklenmeyen backend cevabı
* büyük veri
* yüksek kullanıcı yükü
* kaynakların geç veya hiç yüklenmemesi

Bunların tamamını mekanik olarak test etmek zorunda değilsin. Özelliğe gerçekten uygulanabilir olanları belirle.

---

## 3. Adversarial Review Yap

Önemli bir implementasyondan sonra kod değiştirmeden önce kısa bir adversarial review yap.

Şunları ara:

* mantık hataları
* yanlış varsayımlar
* gizli bağımlılıklar
* state tutarsızlıkları
* hata yönetimi eksikleri
* veri kaybı ihtimali
* güvenlik problemleri
* performans darboğazları
* race condition
* kullanıcıyı kilitleyen durumlar
* sessizce başarısız olan işlemler
* gözden kaçmış edge case'ler

Kendi çözümünü savunmaya çalışma.

---

## 4. Regresyonu Önle

Bir bug veya özellik üzerinde çalışırken yalnızca yeni davranışın çalışmasını kontrol etme.

Değişiklikten etkilenebilecek mevcut davranışları da belirle.

Kod değişikliğinden sonra:

1. Yeni davranışı doğrula.
2. İlgili eski testleri çalıştır.
3. Mümkünse tüm uygun test suite'ini çalıştır.
4. Daha önce çalışan davranışların bozulmadığını kontrol et.

Bir bug'ı düzeltmek için alakasız alanları yeniden tasarlama.

---

## 5. Minimum Scope Değişikliği

Görev için gerekli olmayan dosyalara, mimariye veya davranışlara dokunma.

Tercih sırası:

1. problemi anlamak
2. root cause'u bulmak
3. minimum güvenli değişiklik
4. doğrulama

"Nasıl olsa buradayken bunu da düzeltelim" yaklaşımından kaçın.

Refactor gerekiyorsa görev kapsamından ayrı olduğunu belirt.

---

## 6. Testleri Implementasyona Uydurma

Bir test başarısız olduğunda testi doğrudan değiştirme.

Önce şu soruyu cevapla:

> Hatalı olan implementation mı, test mi?

Test yalnızca gerçekten yanlış expectation içeriyorsa değiştirilmelidir.

Implementation'ın mevcut hatalı davranışını geçirmek için testleri gevşetme veya assertion kaldırma.

---

## 7. Mümkün Olduğunda Test-First Yaklaşımı

Bugfix ve kritik iş mantığında mümkünse:

1. Beklenen davranışı tanımla.
2. Hatanın varlığını gösteren test yaz.
3. Testin başarısız olduğunu doğrula.
4. Minimum production kodu değişikliğini yap.
5. Testin geçtiğini doğrula.
6. Regression testlerini çalıştır.

Test yazılamayan durumlarda bunun nedenini belirt.

---

## 8. Test Coverage ≠ Gerçek Güven

Yüksek coverage tek başına yeterli değildir.

Testlerin sadece satırları çalıştırmasını değil, davranışı doğrulamasını hedefle.

Özellikle şu tür zayıf testlerden kaçın:

* yalnızca fonksiyon çağrıldı mı testi
* anlamlı assertion içermeyen test
* implementation detaylarını birebir kopyalayan test
* gerçek davranış yerine mock'un kendisini test eden test
* her şeyi mock'layıp entegrasyonu hiç test etmeyen test

---

## 9. Mock Kullanımına Dikkat

Mock'lar test izolasyonu için kullanılabilir ancak gerçek entegrasyon problemlerini gizleyebilir.

Önemli akışlarda mümkün olduğunda şu katmanları ayrı düşün:

* unit test
* integration test
* end-to-end test

Her özellik için üçünün de zorunlu olduğunu varsayma; risk seviyesine uygun test türünü seç.

---

## 10. Hata Durumlarını Tasarımın Parçası Kabul Et

Hata yönetimini sonradan eklenen bir detay olarak görme.

Şunları açıkça düşün:

* işlem başarısız olursa kullanıcı ne görür?
* veri hangi durumda kalır?
* retry güvenli mi?
* aynı request tekrar gönderilirse ne olur?
* yarım kalan işlem geri alınabilir mi?
* sistem inconsistent state'e düşebilir mi?
* hata loglanıyor mu?
* hata sessizce yutuluyor mu?

---

## 11. Varsayım Yapma, Doğrula

Kod tabanı hakkında tahmin yürütmeden önce ilgili dosyaları, testleri, type'ları ve mevcut davranışı incele.

Özellikle:

* mevcut API contract
* database schema
* naming conventions
* architecture
* environment configuration
* reusable utilities
* error handling pattern
* mevcut test yapısı

varsa bunlara uy.

Var olan şeyi yeniden implement etme.

---

## 12. Değişiklik Sonrası Zorunlu Verification

Her anlamlı kod değişikliğinin sonunda uygun olan kontrolleri çalıştır:

* unit tests
* integration tests
* type checking
* lint
* build
* ilgili runtime testleri

Sadece "kod doğru görünüyor" diyerek görevi tamamlanmış sayma.

Çalıştırmadığın kontrolleri çalıştırmış gibi söyleme.

---

## 13. Başarıyı Kanıtla

Görevi tamamladığını söylerken mümkünse somut doğrulama sun:

* hangi testler çalıştı
* kaç test geçti / kaldı
* hangi build/lint/typecheck çalıştı
* hangi edge case'ler kontrol edildi

Kontrol edemediğin alanları açıkça belirt.
