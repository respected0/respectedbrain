# Mimari giriş noktası

Yetkili karar kaynağı [Modüler Temel](superpowers/specs/2026-10-03-modular-foundation-design.md) ve [işletim eki](superpowers/specs/2026-10-03-modular-foundation-operations.md) belgeleridir. Uygulama sırası ve canlı devreye alma kapıları [planda](superpowers/plans/2026-10-03-modular-foundation.md) tutulur.

Tek kaynak paketi `src/respectedbrain/` altındadır. `core/` yollar/config/platform/lock sözleşmelerini sunar; özellik modüllerine bağımlı olmaz. `bootstrap.py` bağlamı oluşturur, `cli.py` aynı servisleri komutlara bağlar. `resources/` başlangıç notları, varsayılanlar, instructions ve skills kaynağıdır.

Kullanıcı için klasör açıklaması ve SSS [README](../README.md) içindedir. [Tarihsel mimari](history/2026-10-03/ARCHITECTURE.md) eski düzenin tam metnidir; güncel kurulum talimatı değildir.
