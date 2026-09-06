---
name: yazilim-kalite
description: Kod kalitesi, adversarial review ve verification gate uygular. "kalite kontrol", "yazılım kalite" için kullan.
---

# Yazılım Geliştirme Kalite Kuralları & Golden Standard Gate

Bu skill, RespectedOS altındaki ve bağlı tüm yazılım geliştirme görevlerinde kod kalitesini, hata toleransını, regresyon güvenliğini ve gerçek dünya senaryolarını güvenceye almak için kullanılır.

> **Ana İlke:** Yalnızca çalışan kod üretmek yeterli değildir. AI'nın hedefi salt kod üretmek değil; en küçük güvenli değişiklikle doğru davranışı üretmek, beklenmeyen senaryoları düşünmek, çalışan özellikleri bozmadan sonucu **kanıtlanabilir** şekilde doğrulamaktır.

---

## 1. Zihinsel Rol Değişimi & Adversarial Review

Aynı AI hem implementasyonu hem doğrulamayı yapıyor olsa bile bu iki görevi tek zihinsel adım olarak yürütme:

1. **Önce Geliştirici:** İhtiyaca odaklan ve implementasyonu tamamla.
2. **Sonra Bağımsız Senior Reviewer / QA:** Implementasyon kararlarını savunmayı bırak. Kodu dışarıdan biri yazmış gibi eleştirel gözle incele.
3. **Temel Soru:** *"Bu kod çalışıyor mu?"* değil, **"Bu kod hangi koşullarda bozulabilir?"**
4. **Adversarial Tarama Listesi:**
   - Mantık hataları ve yanlış varsayımlar
   - Gizli bağımlılıklar ve state tutarsızlıkları
   - Hata yönetimi eksikleri ve sessizce yutulan/başarısız olan işlemler
   - Veri kaybı ihtimali ve güvenlik açıkları
   - Race condition, concurrency ve timing sorunları
   - Kullanıcıyı kilitleyen durumlar ve gözden kaçmış edge case'ler

---

## 2. Risk Bazlı Çalışma Matrisi

Her değişikliği aynı ağırlıkta ele alma; inceleme ve test derinliğini risk seviyesine göre ayarla:

| Risk Seviyesi | Kapsam / Örnekler | Zorunlu Süreç |
| :--- | :--- | :--- |
| **Düşük Risk** | Text değişikliği, basit CSS/stil, küçük UI metin/düzenlemesi | Minimum etki analizi, syntax/lint kontrolü, temel görsel/fonksiyonel doğrulama. |
| **Orta Risk** | Yeni component, form validasyon/logic, API kullanım değişikliği, state management değişikliği | Happy path + kritik edge case'ler + regression kontrolü + ilgili birim/entegrasyon testleri. |
| **Yüksek Risk** | Auth, yetkilendirme, ödeme, DB migration/schema, realtime/concurrency, veri silme, kritik algoritmalar, güvenlik sınırları, prod infra | Derin adversarial review, tam Failure Matrix analizi, veri bütünlüğü ve rollback planı, regression testleri ve duman (smoke) doğrulaması. |

---

## 3. Failure Matrix (Kritik Akışlar İçin)

Önemli özelliklerde ve akışlarda şu dört kategoriyi mutlaka değerlendir:

1. **Success (Normal Akış):** Beklenen parametrelerle hatasız tamamlama.
2. **User Error (Kullanıcı Hatası):**
   - Geçersiz/eksik input, null / undefined / empty değerler
   - Sınır değerler (boundary values)
   - Kullanıcının işlemi çok hızlı art arda tetiklemesi (double-click, double-submit)
   - Yanlış işlem sırası, modalı yarıda kapatma
3. **System Failure (Sistem & Altyapı Hatası):**
   - API timeout, network kopması, HTTP 4xx/5xx yanıtları
   - Partial failure (parçalı başarı), retry davranışı
   - Uygulamanın veya alt sürecin aniden sonlanması
   - DB / disk / dosya sistemi hataları
4. **Timing / State Failure (Zamanlama & Durum Hatası):**
   - Race condition, concurrency, lifecycle çakışmaları
   - Stale state, cache tutarsızlıkları, bellek sızıntısı
   - Auth/session süresinin işlem ortasında dolması
   - Beklenmeyen backend payload yapısı, büyük veri boyutu

---

## 4. Test ve Regresyon Disiplini

1. **Minimum Scope:** Görev için gerekli olmayan dosyalara, mimariye veya davranışlara dokunma. *"Nasıl olsa buradayken şunu da düzeltelim"* yaklaşımından kaçın. Refactor gerekiyorsa ayrı kapsam olarak sun.
2. **Testleri Koda Uydurma:** Bir test patladığında testi doğrudan değiştirme. Önce sor: *"Hatalı olan kod mu yoksa test mi?"* Kodu geçirmek için assertion kaldırma veya testi gevşetme.
3. **Test-First (Mümkünse):** Bugfix ve kritik mantıkta: Hatanın varlığını kanıtlayan testi yaz -> başarısız olduğunu gör -> minimum fix yap -> testin geçtiğini gör -> regresyon testlerini çalıştır.
4. **Coverage ≠ Güven:** Sadece fonksiyon çağrıldı mı testi, içi boş assertion, implementation detayını kopyalayan test veya her şeyi körü körüne mock'layan test sahte güvenlik üretir.
5. **Mock Farkındalığı:** Mock'lar dış dünyayı yalıtır ancak gerçek entegrasyon arızalarını gizler. Dış araç/CLI sözleşmelerini parametre silerek çözme (`assertNotIn` tuzağı); gerçek ortamda en az bir duman testiyle doğrula.

---

## 5. Güvenlik, Veri Bütünlüğü, İzlenebilirlik ve Bağımlılıklar

- **Security Verification:** Input sanitization, auth/authz sınırları, privilege escalation, credential/token sızıntısı, hassas verinin loglara basılması, injection riskleri.
- **Data Integrity & Rollback:** Veri silen, güncelleyen veya schema değiştiren işlemlerde transaction zorunluluğu, duplicate/retry durumunda veri bozulması riski, migration geri alınabilirliği (rollback).
- **Observability:** Önemli hatalar yeterli bağlamla loglanıyor mu? Hata sessizce yutuluyor mu? Kullanıcıya sunulan hata mesajı ile geliştirici teşhis bilgisi ayrıldı mı?
- **Dependency & Contract Safety:** Tahminle paket ekleme. Mevcut araçlarla çözülebiliyorsa yeni bağımlılık getirme. API/SDK sürüm ve breaking change uyumluluğunu doğrula.

---

## 6. Golden Standard Completion Gate

Anlamlı bir yazılım geliştirme görevi aşağıdaki kontroller tamamlanmadan **"tamamlandı", "çözüldü", "çalışıyor" veya "done"** ilan edilemez:

### Zorunlu Kontrol Sırası
1. **Requirement Doğrulama:** İhtiyaç ve beklentilerin net anlaşılması.
2. **Implementasyon:** Minimum scope ile temiz kod.
3. **Bağımsız Self-Review:** Tarafsız gözle kod incelemesi.
4. **Adversarial / Failure Analizi:** Failure matrix üzerinden kırma senaryoları.
5. **Relevant Edge-Case Doğrulaması:** Özelliğe uygulanabilir sınır durumlar.
6. **Relevant Automated Tests:** Unit / integration testlerinin çalıştırılması.
7. **Regression Doğrulaması:** Eski çalışan testlerin/özelliklerin bozulmadığının teyidi.
8. **Runtime / Integration Doğrulaması:** İmkan varsa canlı süreç/bağlantı testi.
9. **UI / Visual Doğrulaması:** UI değişikliklerinde render, loading, empty, error, responsive durumları.
10. **Final Evidence Raporu:** Somut kanıtların kullanıcıya sunulması.

---

## 7. Kanıt ve Doğrulama Rapor Formatı (Evidence Rule)

Görev tamamlandığında sonuçlar şu 3 kategoride açıkça raporlanır:

- `VERIFIED`: Gerçekten komutla çalıştırıldı, test edildi veya arayüzde gözlemlendi.
- `INFERRED`: Kod analizi ve mantıksal incelemeye dayanıyor ancak runtime/canlı doğrulaması yapılmadı.
- `NOT VERIFIED`: Ortam kısıtları, eksik araç veya kapsam dışı nedenlerle kontrol edilmedi (nedeni açıkça belirtilir).

### Örnek Kapanış Tablosu

```markdown
### Kalite ve Doğrulama Raporu (Golden Standard)

| Alan | Durum | Detay / Kanıt |
| :--- | :---: | :--- |
| Birim / Entegrasyon Testleri | VERIFIED | 14 test çalıştırıldı, tamamı PASS (0 failure). |
| Regresyon Kontrolü | VERIFIED | Mevcut test suite'i çalıştırıldı, bozulma yok. |
| Edge Cases & Failure Matrix | VERIFIED | Null/empty input ve timeout senaryoları doğrulandı. |
| Typecheck & Lint | VERIFIED | npm run lint / tsc --noEmit hatasız tamamlandı. |
| UI & Responsive Davranış | INFERRED | Component JSX ve CSS incelendi; tarayıcı testi kullanıcı onayı bekliyor. |
| DB Rollback Mekanizması | NOT VERIFIED | Staging ortamı bulunmadığından canlı DB'de denenmedi. |
```
