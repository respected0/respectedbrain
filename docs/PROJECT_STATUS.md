# 📍 Respected Brain — Proje Durumu

scope: project; confidence: verified; supersedes: ["Önceki tarihli uygulama planının aktif durum otoritesi"]

> Aktif durumun tek kaynağı bu belgedir. Tarihli test sonuçları [test matrisinde](TEST-MATRIX.md), ayrıntılı işlem kayıtları [kayıt indeksinde](records/README.md), güvenlik sınırları [SECURITY](SECURITY.md) içinde ve tarihli tam denetim [kayıt denetiminde](records/2026-10-installer-release/REPOSITORY_AUDIT.md) bulunur.

## 1. Kaynak ve yayın durumu — 2026-10-05

Modüler paket, kurulum seçimleri/hız düzeltmeleri ve kaynak temizliği ana checkout'a birleştirildi. Önceki çalışma dalı ve managed worktree kapatıldı; geliştirme kökü `Documents/ChatGPT/secondbrain` klasöründeki main'dir. Eski kaynak dönüşümünün ayrıntıları [uygulama kaydında](records/2026-10-modular-foundation/IMPLEMENTATION.md).

Son doğrulanmış ürün kodu `631c37eda13f569072e0436984cbf19f6b709ba8` için [37318525236 CI koşusu](https://github.com/respected0/respectedbrain/actions/runs/37318525236) 12/12 işi geçti. Kaynak main'e normal push ile gönderildi; tag veya herkese açık yeni release bu kapanışta oluşturulmadı. Daha sonraki belge düzenlemesini bu ürün kodunun native test sonucu gibi sunmayın.

Bu belgeler yeniden düzenlenirken canlı AppData programı ve sağlayıcı kurulum ayarları değiştirilmez. Kullanıcı kasasına program kurulumu, template taşıma veya not sıfırlama uygulanmaz; hafıza protokolünün devir ve belge bağlantısı düzeltmeleri ayrı not güncellemeleridir. Kaynak kodun modüler olması mevcut canlı kurulumun yeni yapıya geçirildiği anlamına gelmez.

## 2. Devreye alma ve rollout durumu

Ürün düzeyinde yeni kurulum (`setup`), güncelleme (`update`), onarım (`repair`), kaldırma (`uninstall`) ve eski kurulumları güvenle dönüştüren geçiş (`migrate`) motorları hazırdır ve doğrulanmıştır. Migration özelliği mevcut kasayı koruma sözleşmesiyle üründe kalır.

Bu bilgisayara özel kişisel devreye alma tercihi Git dışındaki `.local/ROLLOUT.md` yerel kaydındadır; içeriği bu genel durum belgesinde tekrarlanmaz. Kaynak geliştirme çalışmaları canlı kurulum yapma veya mevcut kasayı değiştirme izni değildir. Canlı kurulum öncesinde program/veri kökleri ve sağlayıcı bağlantıları envanterlenmeli; bağımsız dış bağlantılar korunmalıdır.

## 3. Belge düzenleme kararı — 2026-10-05

Kullanıcı süreç aracına göre adlandırılmış repo/yerel klasörlerin kalmasını istemiyor. Onaylı kararlar `decisions/`, tamamlanan işlem ve kanıtlar tarihli `records/` altındadır. Yerel ikili test/yedek dosyaları hash doğrulamalı `.local/archives/` alanında korunur. [İşlem kaydı](records/2026-10-documentation/REORGANIZATION.md) yapılan düzenlemeleri ve doğrulama kapsamını açıklar.

Eski README'nin Türkçe anlatımı, tabloları ve SSS tarzı yeni giriş ve rehberlerde örnek alınır; eski “sıfır maliyet”, tüm sağlayıcılarda aynı sandbox veya doğrulanmamış platform iddiaları güncel bilgi diye taşınmaz. Eksiksiz dosya atlası ve JSON kaynağı korunur.

## 4. Kalan işler

| İş | Sınır / sahip |
| --- | --- |
| Kaynak klasörlerinin kullanıcıyla sonraki incelemesi | Gereksizliği kanıtlanmış dosyalar; kişisel kasa ayrı |
| Yeni native paket ve canlı devreye alma | Kullanıcının son aşaması; geçici kabul, somut backup ve provider testleriyle |
| DNS transport, provider izinleri, secret tarama, release güven zinciri | [Dört açık hardening alanı](SECURITY.md); CI başarısıyla kapanmaz ([tarihli denetim](records/2026-10-installer-release/REPOSITORY_AUDIT.md)) |
| Giriş yapılmış sağlayıcıların gerçek kabulü | Test/fixture yerine gerçek oturum kanıtı gerekir |

## 5. CI ve çalışma kuralları

Çalışma disiplini [AGENTS.md](../AGENTS.md) içinde tanımlıdır: Push sonrasında CI sürekli sorgulanarak beklenmez; bekleme ajanı/otomasyonu başlatılmaz. Sonuç çıkınca kullanıcı yeniden çağırır, o çağrıda gerçek sonuç incelenir. Kullanıcı istemedikçe paralel ajan çalıştırılmaz. Çalışma kayıtlarındaki eski yöntem talimatları bu tercihin üzerine yazamaz.

Aktif durum değişirse bu belge güncellenir; geçmiş sonuçlar tarihli kayıtlarda korunur. Diğer not ve rehberler yeni durum kopyası yazmak yerine buraya bağlanır.
