# 🌱 İlk Çalıştırma ve Kişiselleştirme

> Bu rehber kurulumdan sonrasını anlatır. Önce [native kurulum](SETUP.md) tamamlanır. Aktif kod reposu hafıza kasası yerine kullanılmaz.

## 1. Doğru kasayı doğrulayın

```text
respectedbrain --version
respectedbrain vault list
respectedbrain maps --vault-id <UUID>
```

Liste kasa UUID'sini ve kayıtlı konumunu gösterir. Maps işlemi not/skill haritaları üretir; salt okunur listeleme değildir. Kasa kaydı tek başına motor kurmaz. Geçersiz açık UUID/yol başka kasaya sessiz geçmez.

## 2. Kendi kimliğinizi yerleştirin

Kasayı Obsidian'da klasör olarak açın. `🔮 850-Companion/Core.md` kişisel bağlam/companion kimliği, `Kurallar.md` kalıcı çalışma tercihleri, `Threads.md` açık konular, `Last-Session.md` devir notudur. Başlangıç placeholder'ları kurulum profiliyle doldurulur; eksik kişisel alanlar kendi notunuzda düzenlenebilir.

Hafıza klasörü programın sabit note sözleşmesinde `🔮 850-Companion` olur; görünen AI adı içeriğe yazılır. Kasa adı serbesttir. Üretilmiş provider adaptörlerini ayrı ayrı elle düzenlemek yerine [tek instruction/skill kaynağı ve override](MULTI_AI.md) akışını kullanın.

## 3. Sağlayıcı ve bağlantı

İstediğiniz yerel CLI'da oturum açın. Örneğin:

```text
respectedbrain configure --summary-provider auto
```

Bu komut DataRoot preferences'ını değiştirir. IDE hook güveni/reload'u gerektiğinde editörün kendi arayüzünden tamamlayın; login ya da güveni config'e provider adı yazmak sağlamaz. Global/MCP/zamanlayıcı isteğe bağlıdır; [çoklu AI rehberine](MULTI_AI.md) bakın.

## 4. Bir gerçek konuşmayı doğrulayın

1. Entegrasyonu açık ajanınızda kısa, anlamlı bir konuşma yapın.
2. Desteklenen tamamlanmış-turn hook'unun tetiklendiğini ve ilgili kasa daily dosyasına özet geldiğini kontrol edin.
3. Özetin konuşmayı doğru temsil ettiğini okuyun; biçim testleri içerik doğruluğunu garanti etmez.
4. Başka ajan da kullanacaksanız onun aynı kasa bağlamını aldığını ayrı oturumda kontrol edin.

Dosyanın aynı gün var olması bu konuşmanın yakalandığını kanıtlamaz; session bloğu/konu ve ilgili logları eşleştirin. Sabit “birkaç saniyede mutlaka olur” süresi yoktur: CLI, ağ, model, kota ve disk etkiler. Başarısızlıkta [sorun giderme](TROUBLESHOOTING.md); sonraki kullanım [günlük rehberde](DAILY_USE.md).
