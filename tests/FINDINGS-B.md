# FINDINGS-B — upgrade settings regresyonları

> Tarihsel ve çözülmüş regresyon kaydıdır; kurulum talimatı olarak kullanılmamalıdır.

## B-1 — İzlenen `settings.local.json` finalize aşamasını kilitliyordu

**Durum:** Mevcut worktree'de eşzamanlı başka bir değişiklikle çözülmüş.

İlk hermetik koşuda v1 fixture'ın `.claude/settings.local.json` dosyası başlangıç
commit'ine zorla alındığında `apply` tamamlandı; fakat `finalize`, `git add -u`
sonrası bu dosyayı yeniden sahneleyip güvenlik kapısında çıkış 1 ile durdu:

```text
Sahnelenmesi yasak dosyalar bulundu ve sahne temizlendi:
.claude/settings.local.json
HATA: sır taşıyabilecek dosya commit'e girmek üzereydi, yükseltme durduruldu
```

Test yazımı sürerken bu lane dışında `scripts/upgrade.sh` değişti. Mevcut sürüm,
önceden izlenen secret dosyalarını diskte tutarak index'ten çıkarıyor ve sahnelenmiş
silme işlemini sızıntı saymıyor. Son koşuda ilgili tam-zincir testleri geçti.

## B-2 — Nesne olmayan local settings Python traceback sızdırıyordu

**Durum:** Mevcut worktree'de eşzamanlı başka bir değişiklikle çözülmüş.

İlk koşuda `--bad-local` fixture'ı `AttributeError` kaynaklı Python traceback'i
kullanıcıya sızdırdı. Test yazımı sürerken bu lane dışında eklenen erken doğrulama,
dosyanın JSON nesnesi olmadığını Türkçe ve anlaşılır bir mesajla bildirip hiçbir
mutasyon yapmadan çıkış 1 veriyor. Son koşuda test 10 geçti.

Bu lane `scripts/upgrade.sh` dosyasını değiştirmedi. Son doğrulama:
`bash tests/upgrade_settings_test.sh` → **12/12 geçti**.
