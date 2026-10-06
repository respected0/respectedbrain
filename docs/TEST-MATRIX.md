# ✅ Test Matrisi ve Kanıtın Sınırları

> Bu belge bir test koşusu çalıştırmaz. Sonuçlar tarih ve ürün kodu ile belirtilir; aktif durum [PROJECT_STATUS](PROJECT_STATUS.md), ayrıntı [çalışma kayıtlarında](records/README.md).

## 1. Son doğrulanmış ürün kodu

2026-10-05 kapanışında `631c37eda13f569072e0436984cbf19f6b709ba8` için [CI 37318525236](https://github.com/respected0/respectedbrain/actions/runs/37318525236) **12/12 job başarılı** kaydedildi. Bu, eski Eylül testlerinin yeni sayıya çevrilmesi değildir. Sonraki doküman değişiklikleri bu commit'in native binary testine dahilmiş gibi sunulmaz.

| Kapı | OS / Python | Kayıtlı sonuç |
| --- | --- | --- |
| Early compatibility | Windows, Linux, macOS / 3.10 | 3 başarılı iş |
| Native build/verify/host kabul ve yayın biçimi | Windows, Linux, macOS / 3.13 | 3 başarılı iş |
| Full source | Windows, Linux, macOS × 3.10 / 3.13 | 6 başarılı iş |

Bu job sayısı birleştirilmiş tek bir toplam test sayısı değildir. Adım/host skip kapsamı ayrıntılı kayıtlarda korunur. Windows gerçek Inno/launcher/scheduler; macOS mounted DMG; Linux extracted makeself kapıları workflow ve native kayıtlarda yer alır.

## 2. Neyi hangi test kanıtlar?

| Test sınıfı | Kanıtlar | Tek başına kanıtlamaz |
| --- | --- | --- |
| Unit/fixture | Algoritma ve arayüz/assertion davranışı | Gerçek provider hesabı veya her OS |
| Wheel isolation | Checkout/PYTHONPATH'ten bağımsız paket import'u | Native kurucu veya Windows receipt |
| Frozen verify | Paket launcher/resources/CLI smoke | Yayıncı imzası veya gerçek AI cevap kalitesi |
| Native kabul | İlgili hostta geçici install/update/uninstall, sahiplik ve rollback | Kullanıcının mevcut canlı kasasının kurulduğu |
| Shell/WSL smoke | İlgili çalıştırıcı/köprü akışı | Giriş yapılmış bütün sağlayıcılar |
| Provider adapter testi | Hook/JSON/argv sözleşmesi | Güncel dış ürün sürümündeki gerçek login/kota/izin |

CI runner'da gerçek OS yürütülmesi yalnız fixture OS taklidinden güçlüdür; kullanıcı masaüstündeki GUI/onay/giriş kabulüyle yine aynı şey değildir. Sadece Windows'ta geçen test fiziksel macOS/Linux/WSL kanıtı sayılmaz.

## 3. Gerçek sağlayıcı kabulü

Codex/Antigravity ile bu geliştirme sürecinde oturum akışı gözlemleri bulunur; bütün ajanların son native sürümde kullanıcı hesabıyla acceptance'ı topluca doğrulanmış sayılmaz. Gerçek kabul, doğru UUID ile test konuşmasının hook/daily/ikinci ajan bağlamına yansımasıdır. [BOOTSTRAP](guides/BOOTSTRAP.md) kontrol sırasını anlatır.

## 4. Tarihli kanıt kayıtları

| Kayıt | Kapsam |
| --- | --- |
| [Modüler temel doğrulaması](records/2026-10-modular-foundation/VERIFICATION.md) | İlk source/Windows native ve salt okunur eski canlı envanter; o tarihin platform sınırları |
| [Kaynak temizliği doğrulaması](records/2026-10-source-cleanup/VERIFICATION.md) | Eski kaynak kapanışı ve paket/shell/yedek kanıtı |
| [Installer/atlas/yayın kaydı](records/2026-10-installer-release/EXECUTION.md) | Son gerçek CI, Python sürüm/alias/race araştırmaları ve worktree kapanışı |
| `records/2026-09-legacy/TEST-MATRIX.md` | Yerel arşiv yedeğinde; önceki layout, 370 test ve eski host/provider gözlemleri (tarihsel referans) |
| [Belge düzenleme doğrulaması](records/2026-10-documentation/REORGANIZATION.md) | Doküman yolları, atlas, komut örnekleri ve yerel yedek arşivi |

## 5. Çalıştırma girişleri

```text
python tests/run_all.py --python-only
python tools/verify_distribution.py --platform windows --distribution dist/RespectedBrain
python tests/smoke/platform_smoke.py --package dist/RespectedBrain --output native-smoke.json
```

İlgili OS/native artifact gerekir. Windows kabul `tests/install_windows_test.ps1`, `windows_launchers_test.ps1`, `briefing_schedule_windows_test.ps1`; POSIX hook/upstream testleri shell girişleridir. [Smoke rehberi](../tests/smoke/README.md) komutları, workflow gerçek CI sırasını tanımlar. Çalıştırılmayan testler başarılı diye kaydedilmez. Token/maliyet tercihi nedeniyle push sonrası sonuç bekleme döngüsü kurulmaz.
