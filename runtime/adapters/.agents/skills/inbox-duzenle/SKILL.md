---
name: inbox-duzenle
description: Gelen kutusu ve Dump notlarını tasnif edip düzenler. "inbox düzenle", "dump temizle", "triyaj" dendiğinde kullan.
---

# Inbox Düzenleme

## İlke

`📥 000-Inbox/Dump/` içeriğini önce salt okunur incele. Kullanıcı açıkça onaylamadan hiçbir notu
yeniden adlandırma, taşıma, düzenleme veya silme.

## Zorunlu akış

1. Dump altındaki normal dosyaları listele. Symlink/reparse point veya Dump dışına çözülen yolu
   reddet.
2. Her not için içeriği oku ve şu önizleme tablosunu üret:

   `ID | Mevcut yol | SHA-256 | Önerilen başlık | Hedef klasör | Etiketler | Bağlantılar | Gerekçe`

3. Hedef yolu vault köküne göre yaz. Var olan bir hedefe overwrite önerme; bunun yerine çakışmayı
   raporla.
4. Önizlemeden sonra dur ve kullanıcının uygulamak istediği ID'leri açıkça onaylamasını bekle.
   “Devam”, “hallet” gibi belirsiz yanıtlar onay değildir.
5. Önizlemede her kaynak dosyanın tam SHA-256 değerini baseline olarak kaydet. Onay gelirse yalnız
   seçilen ID'leri uygula. Önce SHA-256 değerini yeniden hesapla ve baseline ile tam eşitlik ara;
   önizlemeden beri değişen dosyayı atla ve raporla.
6. Uygulama başlamadan tüm kaynak içeriklerini bellekte tut. Hedef yokluğunu yeniden doğrula.
   Batch içinde hata olursa bu içeriklerle yapılan değişiklikleri geri al ve yarım başarı bildirme.
7. Başlık/frontmatter güncellemesinde mevcut anlamlı metadata'yı koru. Etiketleri birleştir,
   wikilinkleri yalnız gerçekten ilişkili notlara ekle.
8. Başarılı batch sonunda `python3 .beyin/map_builder.py` çalıştır. Kullanıcıya taşınan, atlanan ve
   değişmeden bırakılan ID'leri bildir.

## Kırmızı çizgiler

- Açık onay olmadan yazma yok.
- Kullanıcı ayrıca istemedikçe kalıcı silme yok.
- Hedef dosyanın üzerine yazma yok.
- Onaylanmayan ID'ye dokunma yok.
- Kaynak değişmişse eski önizlemeyi uygulama yok.

## Kısa hüküm

Önizleme bir öneridir; onay yalnız belirtilen ID'ler için tek uygulama yetkisidir.
