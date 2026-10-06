# Respected Brain kaynak deposu çalışma kuralları

Proje gerçeğini güncel dosyalardan doğrula. Onaylı mimari `docs/decisions/`,
aktif ürün durumu `docs/PROJECT_STATUS.md` içindedir. Bu bilgisayara özel
devreye alma kararı Git dışındaki `.local/ROLLOUT.md` kaydındadır.
Kullanıcının canlı programını veya not kasasını kaynak işi sırasında değiştirme.

## Dosya haritasını aynı değişiklikte güncelle

- Bir dosya eklediğinde, sildiğinde, taşıdığında veya sorumluluğunu değiştirdiğinde
  `docs/repository_inventory.json` açıklamasını aynı görev içinde güncelle.
  Kullanıcıdan hatırlatma bekleme. Dosyanın güncel içeriğini ve çağıranlarını oku.
- `python tools/repository_map.py --update` ile yeni dosyaları keşfet; yeni
  `NEEDS_REVIEW` kayıtlarının rol, amaç ve ilişkilerini gerçek içerikle doldur.
- Açıklamasını gözden geçirdiğin her değişen dosya için
  `python tools/repository_map.py --accept-reviewed <dosya>` çalıştır.
  Yalnız hash yenileyerek içerik incelemesini atlama.
- `python tools/repository_map.py --write` ile `docs/REPOSITORY_MAP.md` üret;
  üretilmiş Markdown'ı elle düzenleme.
- `python tools/repository_map.py --check` ve değişiklikle ilgili anlamlı
  kontroller geçmeden tamamlandı deme. CI aynı atlas kapısını zorunlu tutar.
- Bağımlılık, build/cache ve canlı kullanıcı dosyaları kaynak envanterine
  alınmaz. Yeni dosyanın ignore edilmesini açıklama eksikliğini gizlemek için
  kullanma.

## Kaynak ve kurulu ürün sınırları

Ürün kodu `src/respectedbrain/`, immutable hazır içerik `resources/`, paket
tarifleri `packaging/`, geliştirici araçları `tools/` altında kalır. AppRoot,
DataRoot ve VaultRoot birbirinden ayrıdır. Güncelleme/kaldırma insan notlarını
üzerine yazmaz; sahiplik, işlem günlüğü ve geri alma korumaları korunur.

## Push sonrası CI takibi

Kullanıcı tercihi (2026-10-05): push sonrasında CI sonucunu sürekli sorgulayarak
bekleme; bunun için ajan veya otomasyon başlatma. Sonuç çıktığında kullanıcı
yeniden çağırır, o çağrıda sonucu incele. Doğrulanmamış CI sonucunu başarılı
veya main birleştirmesini tamamlanmış olarak bildirme.

## Belge düzeni

Kullanıcı süreç aracı adı taşıyan repo/yerel klasör istemiyor. Yeni çalışma kararları docs/decisions, tamamlanmış uygulama/kanıt kayıtları docs/records altında tutulur. Yerel ikili yedek ve test kanıtları .local/archives içindedir; kaynak envanteri veya kişisel kasa değildir. Aktif durum yalnız docs/PROJECT_STATUS.md içindedir. Yeni belgeler doğrulanmış kod ile hedef/tarihsel kaydı ayırır; dosya atlası korunur. Kullanıcı istemedikçe paralel ajan çalıştırma.
