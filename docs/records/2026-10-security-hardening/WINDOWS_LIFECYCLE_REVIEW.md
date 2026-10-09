# Windows yaşam döngüsü teslim incelemesi — 2026-10-08

scope: project; confidence: verified; supersedes: ["Windows yaşam döngüsü tamamlandı; yalnız gerçek yayın imzası kaldı iddiası"]

Bu kayıt GLM tesliminin bağımsız kontrolüdür; aktif durum [PROJECT_STATUS](../../PROJECT_STATUS.md) içindedir. Ürün kodu değiştirilmedi. Genel kabul verilmedi.

## Doğrulanan kapsam

`security_hardening_fifth_fix_test`, `foundation_inno_service_test`, `release_provenance_test`, `provenance_lifecycle_transport_test`, `repository_map_test`: **49/49 OK**, 14.614 s, Python 3.12.14. İlk sandbox koşusu geçici dosya erişim/cleanup hataları verdi; aynı testler sandbox dışında geçti. Tam suite ve native Inno round-trip yeniden çalıştırılmadı.

Kaynakta zorunlu `prepare_shell(package=...)`, normal CLI'da strict provenance, doğrulanmış kaynaktan helper ve receipt hata yakalama değişiklikleri mevcut. Pozitif provenance testleri fixture verifier kullanır; gerçek kriptografik yayın kanıtı değildir. İlk kullanım için `welcome` ve kasa/ad/biyografi/Companion alanları kaynakta var; son EXE'de bu yeni akışın tamamı henüz doğrulanmadı.

Bağımsız kanıtlar `.local/archives/2026-10-08-lifecycle-review/` altında: `targeted-unsandboxed.log`, `source_compare.json`, `probes.json`, `owned_hooks.json`, `git_before.json`. Sonraki doğrulama eski sonuç dosyalarının üzerine yazmamalıdır.

## Teslim bulguları

1. **P2 — Paket son kaynakla eşit değil.** Python 3.13 frozen PYZ, aynı sürüm interpreter ile opcode/sabit/nested code/closure/exception table/stack size düzeyinde karşılaştırıldı. 84 modülde 81 eşit; `respectedbrain.cli`, `respectedbrain.installation.windows`, `respectedbrain.installation.wizard` farklı. EXE 00:36:32; kaynak CLI/Windows 01:32 tarihli. Timestamp tek kanıt değildir; semantic fark doğrudan doğrulandı.
2. **Teslim engeli — Mevcut paket gerçek kurulumu geçmiyor.** Attestation sidecar yok. Gerçek EXE `_inno-prepare`, geçici app/data/vault kökleriyle exit 1 verdi: `Missing build provenance attestation file; fail-closed`. Başarısız receipt yazıldı; app/vault/request oluşmadı. Güvenli ret doğru davranıştır, fakat bu artifact kurulabilir ürün değildir. Bunu yalnız kozmetik yayın işi gibi sunmayın; bypass eklemeyin.
3. **P2 — Deferred CLI uninstall temizliği kapatıyor.** Parser `keep_data=False` üretirken dispatch `getattr(args, 'purge_data', False)` kullanıyor. `cli.main(['uninstall'])` girişinde deferred çağrı `purge_data=False` aldı. Frozen EXE'nin kendi kaldırma yolunda varsayılan teknik temizleme tercihi kayboluyor; GUI/Windows uygulama listesi yolu ile aynı davranmıyor. Normal, `--keep-data` ve uyumluluk `--purge-data` girişleri final receipt'e kadar aynı tercihi taşımalı.
4. **P2 — Kaldırma yerel AI hook'larını bırakıyor.** İzole kaynak fixture'ında setup ve uninstall success=true, conflict=[] verdi; buna rağmen `.agents/hooks.json`, `.claude/settings.json`, `.codex/hooks.json`, `.cursor/hooks.json`, `.gemini/settings.json` içindeki uygulama EXE'sine bağlı hook'lar kaldı. İnsan notu korundu. Yeni kasa hook'ları kurulurken yaşam döngüsü sahipliği kaydedilmiyor; notların korunması uygulamanın eklediği bağlantıların temizlenmemesini haklı kılmaz. Karma kullanıcı ayarlarında yalnız uygulamanın sahip olduğu girdiler geri alınmalıdır.

## Tek düzeltme ve kabul sırası

1. İki kaynak kaldırma bulgusu için başarısız regresyonları oluştur, minimum düzeltmeyi yap. Başka araçların hook/MCP/skill ayarları ve insan notları korunmalı; değiştirilmiş/bilinmeyen içerik için conflict davranışı doğrulanmalı. Kaynak geçtikten sonra EXE/Setup yeniden üretilsin; 84/84 karşılaştırma ve yeni hash kaydı yapılsın.
2. İlk kullanım kişiselleştirmesinin açılması, kaydedilmesi ve yeniden açılışta tekrar sorulmaması gerçek yeni paketle kontrol edilsin. Repair/update tercihleri ve notları korumalı; bozuk uygulama dosyası doğrulanmış repair paketiyle onarılmalı. Uninstall'da owned bağlantıların gerçekten temizlendiği incelensin; yalnız exit 0 yeterli değil.
3. Kaynak/fixture kapılarından sonra commit/push için kullanıcı talimatı alınsın. Mevcut release workflow yalnız tag ref üzerinde build yapıyor; sıradan main push gerçek attestation üretmez. Kullanıcı yayın adımını yetkilendirirse gerçek tag workflow kanıtlı paket üretmeli; Authenticode kapsamı ayrıca doğrulanmalı. CI bekleme döngüsü başlatılmasın; sonucu kullanıcı yeniden getirsin.
4. Gerçek güven kanıtlı son artifact ile geçici köklerde kurulum → kişiselleştirme → repair → update → uninstall ve hata/rollback kabulü yapılsın. Fixture attestation kullanılarak yapılan test gerçek yayın kabulü sayılmasın. Canlı provider/OS sınırı ve kişisel rollout ayrı kabul kalır.

Commit/push/tag, canlı kurulum/kasa/provider değişikliği, paralel ajan veya CI polling yapılmadı. Başlangıç staged/index durumu korunmalıdır; inceleme için kullanıcı staging'i değiştirilmez.

## For future agent

49 hedefli testin geçmesi ürün kabulü değildir: üç modül pakette eski, unsigned paket preflight'ta reddediliyor ve iki kaldırma hatası bağımsız olarak üretildi. Önce iki kaynak hatasını düzelt, paketi eşitle, ardından gerçek yayın kanıtlı artifact ile geçici kabul yap; aktif durumun tek kaynağı PROJECT_STATUS'dır.
