# Son kaynak temizliği

scope: project; confidence: verified; supersedes: []

Onay: Kullanıcı önceki mesajda sunulan kaynak temizliğini "son temizliği halledelim"
ile seçti. Yeni mimari yok; onaylı modüler temelin eksik kalan kaynak ve yayın
yerleşimi tamamlanır. Canlı kurulum, migration, push ve yayın bu işin dışındadır.

- [x] Eski girişlere bağlı testleri ortak paket/CLI'a bağla; aynı davranışları koru.
- [x] `runtime/`, `installer/`, kök `setup.py/setup/setup.command` geçiş katmanını kaldır.
- [x] Release akışını native build/verify araçlarına bağla; kaynak ağacı paketlenmesin.
- [x] Wheel, Windows native paket, tam testler ve shell fixture'larını doğrula.
- [ ] Son inceleme, yerel ana projeye bütünleştirme ve güncel devir.

Riskler: adapter testlerini kaldırırken güvenlik davranışlarını kaybetmek;
setuptools `setup.py` olmadan wheel/sdist üretiminin bozulması; yayın arşivinin
launcher izinlerini veya kurucu girişini kaybetmesi. Doğrulamalar bu üç riski kapsar.

## Çalışma kaydı

- Başlangıç: `bc8d40a`, izole `codex/source-cleanup`; ilgili 14 test OK.
- Ana projedeki önceki açıklama/plan düzeltmesi korunacak.
- Eski kurulumları okuyabilen migration kodu ve fixture'ları korunacak;
  kaynakta legacy kelimesi/yolu bulunması tek başına silme gerekçesi değildir.
- Linux/macOS yayın tarifleri yerel Windows hostunda fiziksel çalıştırılamaz;
  bu sınır teslimde belirtilir.

## For future agent
Bu iş yalnız kaynak ağacının son temizliği ve yayın tariflerini kapsar.
Canlı geçiş engelleri ana modular-foundation planındadır; onları zorla aşma.

## Doğrulama kaydı — 2026-10-04

629 test, 473.677 saniye, OK (15 atlama). Windows native build ve frozen
version/registry/maps/search/hook/MCP OK; wheel ve sdist OK. Hook fixture 8/8,
upstream fixture 9/9. Release YAML, matrix ve Bash/PowerShell syntax OK.
Fresh son inceleme 39 test çalıştırdı; ürün regresyonu bulmadı.

Küçük ertelenen test notu: runtime_layout_test içinde reload sınıf kimliklerini
değiştirebilir; gelecekte subprocess import probe kullanılabilir. Şu tam suite
başarılıdır. Mevcut GUI CLI-vault/package forwarding sorunu bu değişiklikle
oluşmadı; davranış geliştirme aşamasında ele alınır.
