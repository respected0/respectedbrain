# Son kaynak temizliği — 2026-10-04

scope: project; confidence: verified; supersedes: []

Kullanıcının "son temizliği halledelim" isteğiyle onaylı modüler temelin
geçiş katmanı kaldırıldı. `runtime/`, `installer/`, kök `setup.py`, `setup`,
`setup.command` artık kaynak girişleri değildir. `src/respectedbrain` tek
pakettir. Eski canlı kurulumları okuyabilen migration modülleri korunmuştur.

## Kaynak ve yayın kontrolleri

- CLI güvenlik/durum testleri eski dosya yüklemek yerine ortak CLI'ı çağırır.
  Kullanıcı notlarını koruma, bilinmeyen eski seçenekleri reddetme ve migration
  varsayılan önizleme davranışları korunmuştur.
- Test başlangıcındaki runtime/scripts sys.path ve scripts alias'ları kaldırıldı.
- Release artık her native hostta build, verify, tam test ve platform smoke
  çalıştırır; exe/dmg/run kaynak checkout yerine native dağıtım içerir.
- Yayın tag'i paket sürümüyle eşleşmek zorundadır. Smoke kanıtları yayın
  dosyalarıyla karışmaz; publish yalnız başarılı build matrix'ine bağlıdır.
- Fresh dev ortamında wheel eksikliği yeniden üretildi; dev extra ve source CI
  build testlerinin bağımlılıklarını kurar. README aynı geliştirme komutunu verir.
- `.superpowers/`, release staging ve release outputs kaynak kontrolünden hariçtir.

## Gerçek komut sonuçları

- `python -m unittest discover -v -s tests -p '*test*.py'`:
  **629 test, 473.677 saniye, OK (skipped=15)**.
- Native Windows PyInstaller + Inno build: OK.
- `tools/verify_distribution.py`: frozen version/registry/maps/search/hook/MCP OK;
  sistem Python PATH'i yok, not fixture'ı aynı kaldı.
- Wheel ve sdist build: OK; arşivde runtime/installer veya kök setup girişleri yok.
- `tests/hooks_test.sh`: 8/8 OK; `tests/upstream_sync_test.sh`: 9/9 OK.
- Release YAML parse, üç host matrix, publish bağımlılığı, Bash ve PowerShell
  syntax doğrulaması: OK. `git diff --check`: OK.
- Bağımsız son inceleme: 39 dar test OK, yeni ürün regresyonu bulunmadı.

GitHub Actions gerçek koşusu veya macOS/Linux fiziksel yayın paketi bu yerel
Windows çalışmasında çalıştırılmadı. Tarihli kaynak doğrulaması gerçek CI koşusu
yerine geçmez. Action major sürümleri resmi release sayfalarında doğrulandı:
[checkout](https://github.com/actions/checkout/releases),
[setup-python](https://github.com/actions/setup-python/releases),
[upload-artifact](https://github.com/actions/upload-artifact/releases),
[download-artifact](https://github.com/actions/download-artifact/releases).

## Yerel yedek ve sınırlar

Ana checkout'ın eski kaynak/önbellekleri ve açıklama planı toplam 177 dosya olarak
ignored `.superpowers/sdd/2026-10-04-source-cleanup-backup/files/` alanına kopyalandı;
her dosya hash eşitliğiyle doğrulandı. Eski runtime/state altındaki üç untracked
teknik dosya da yedeklidir. Compile kilidinin mevcut tutucusu bulunmadı.
Canlı AppData kurulumu, RespectedOS kasası ve dış AI ayarları bu temizliğin hedefi değildir.

Küçük ertelenen test notu: runtime_layout_test içindeki in-process reload, sınıf
kimliklerini yeniden oluşturur; ileride subprocess import probe daha iyi izolasyon
sağlar. Tam suite şu değişiklikle başarılıdır. GUI setup'ın CLI vault/package
seçeneklerini wizard'a iletmemesi mevcut sorundur; kaynak temizliği bunu değiştirmedi.

## Yerel bütünleştirme

Main, `bc8d40a` → `7b1174d` fast-forward ile ilerledi. Önceki açıklama/plan
değişikliği birebir yedekle karşılaştırılıp temizlik commit'ine dahil edildi.
Eski köklerin kalan teknik kayıt/bytecode dosyaları backup manifest'ine göre
yeniden hash kontrolünden geçtikten sonra kaldırıldı. Ana klasörde retired
runtime/installer/template ve kök setup girişlerinin hiçbiri yoktur.

Ana klasörde 40 ek paket/wheel/CLI davranış testi OK (24.045 saniye). Frozen
native version/registry/maps/search/hook/MCP kontrolü tekrar OK. Tam 629 test
koşusu aynı ürün/test kaynaklarını taşıyan izole commit üzerinde yapılmıştır.
1068 paket dosyası ana dist alanına kopyalanıp birebir hash eşitliği doğrulandı;
önceki dist, ignored backup/previous-dist alanında korundu. Geliştirme venv'i
ana src paketine bağlıdır; bu canlı ürün kurulumu değildir. Test/derleme kanıtları
ignored `.superpowers/sdd/2026-10-04-source-cleanup/` alanında tutulur.

Managed çalışma kopyası arşivlendi; git worktree list yalnız ana checkout'ı
gösterir. Birleşmiş geçici dal silindi. GitHub push/yayın yapılmadı.

## For future agent
Aktif durum ana modular-foundation planındadır; bu belge tarihli kanıttır.
Canlı migration engellerini veya GitHub yayınını bu yerel temizlik tamamlandı diye aşma.
