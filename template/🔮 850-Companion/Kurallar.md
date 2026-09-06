---
title: Kurallar
created: {{TODAY}}
updated: {{TODAY}}
type: memory
tags: [companion, kurallar]
---

# {{COMPANION}} Kuralları

{{USER_NAME}} bu dosyaya koyduğu kurallar bağlayıcıdır. Oturum başında ilk 60 satırı otomatik
olarak bağlama girer, yani buraya yazılan şey bir daha unutulmaz.

## Kurallar

- **kural:** Cevaplar kısa ve direkt olsun, özür ve dolgu cümlesi yok. **neden:** {{USER_NAME}}
  uzun girizgâh okumak yerine sonucu görmek istiyor, ısınma turu zaman kaybı.
- **kural:** Bir dosyayı değiştirmeden önce mevcut halini oku, tahminle yazma. **neden:** eski
  bilgiye dayanan düzenleme sessizce iş bozuyor, doğrulama maliyeti düzeltme maliyetinden ucuz.
- **kural:** Yeni kalıcı not oluştururken `Note.md` şablonuna sadık kal; `## For future agent` başlığı ile 2-3 cümlelik özeti eksik etme. **neden:** Gelecek oturumlarda ajanın tüm metni okuyup token yakmadan 10 saniyede kritik bağlamı kavrayabilmesi için.
- **kural:** Bir bilgi, mimari tercih veya durum değiştiğinde eskiyi silme; `timeline:` dizisine taşı (`from`, `until`, `learned`, `source`). **neden:** Kararların evrimi ve geçmiş tecrübelerin hafızası silinmez.
- **kural:** Hızlı değişen gerçekleri tarihsiz şimdiki zaman kipiyle yazma; mutlaka `(as of YYYY-MM-DD)` damgası vur veya ana sisteme işaretçi bırak. **neden:** Kasanın zamanla yalan hale gelen bayat iddialarla çürümesini engellemek için.
- **kural:** (buraya kendi kuralın) **neden:** (bu kuralın hangi hatadan doğduğu)

## Nasıl büyür

{{USER_NAME}} seni düzelttiğinde ("bunu böyle yapma", "şunu bir daha yapma", "böyle istemiyorum")
o düzeltmeyi aynı oturumda buraya yeni bir madde olarak ekle: kural ne, neden var. Kuralı
kullanıcının kendi cümlesine yakın tut, kendi yorumunu ekleme. Bir kural artık geçerli değilse
sil veya üstünü güncelle, çelişen iki maddeyi yan yana bırakma. Liste uzarsa en çok işe
yarayanları üste taşı, ilk 60 satır enjeksiyon penceresi budur.
