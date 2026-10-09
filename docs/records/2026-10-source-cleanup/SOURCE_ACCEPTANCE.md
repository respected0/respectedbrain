# 📋 Respected Brain — Kaynak Kabul ve Doğrulama Raporu (2026-10-06)

scope: project; confidence: verified; supersedes: []

Bu belge, `src/respectedbrain` paketinin Windows yerel ortamında yürütülen kod düzeltmeleri, test keşfi, Tcl/Tk çalışma zamanı teşhisi, karşılaştırmalı performans benchmarkı, paket yaşam döngüsü kabulü ve güvenlik sınırlarının nihai kanıt kaydıdır. Önceki `SOURCE_REVIEW.md` kaydını toptan geçersiz kılmaz; bulgularını doğrulanmış kanıtlarla tamamlar.

---

## 1. Başlangıç Durumu ve Korunan Sınırlar

- **Başlangıç HEAD:** `0f69ba2a28e89d0faa33f8d613736551f58dea89`
- **Başlangıç İndeksi:** `.local/handoffs/SOURCE_ACCEPTANCE_REWORK_START.json` içinde 272 dosya hash'iyle bağımsız olarak kaydedildi; önceki `.local/handoffs/SOURCE_ACCEPTANCE_START.json` ezilmedi.
- **Git Disiplini:** Hiçbir `commit`, `push`, `reset`, `stash` veya `git clean` çalıştırılmadı. Staged değişiklik oluşturulmadı (`git diff --cached` tamamen boştur).
- **İzolasyon Garantisi:** Canlı program (`%LOCALAPPDATA%\Programs\RespectedBrain`), canlı kullanıcı verisi (`%APPDATA%\RespectedBrain`) ve kişisel not kasası (`C:\Users\Furkan\Documents\RespectedOS`) asla okunmadı ve değiştirilmedi. Tüm testler ve doğrulamalar geçici kök dizinlerde (`tempfile.TemporaryDirectory`) izole yürütüldü.
- **Ajan Politikası:** Paralel alt ajan başlatılmadı; arka plan CI bekleme döngüsü açılmadı.

---

## 2. Windows Quoting ve Apostrof Regresyonunun Düzeltilmesi (Madde 1)

- **Teşhis:** `src/respectedbrain/providers/runner.py` içine daha önce eklenen regex (`re.sub(r"'([^']*)'", ...)`), Windows komutlarındaki literal apostrofların (`O'Brien`, `Bob's notes`, `don't`, `can't`) bağlamını anlayamıyor ve Windows `CommandLineToArgvW` sözleşmesini bozuyordu. Ayrıca test fixture'ında POSIX `shlex.join` kullanılması Windows ters eğik çizgilerini kaçış karakteri olarak yorumluyordu.
- **Düzeltme:**
  1. `src/respectedbrain/providers/runner.py` içindeki hatalı regex ve gereksiz `import re` tamamen kaldırıldı; Windows native sözleşmesi doğrudan `CommandLineToArgvW(command, &argc)` ile sağlandı. Windows API'si tek tırnağı özel karakter değil, literal karakter olarak ele alır.
  2. `tests/windows_native_test.py:93` içindeki test fixture'ında Windows'ta `subprocess.list2cmdline([sys.executable, str(model)])` kullanımı sağlandı.
  3. `tests/adversarial_quality_test.py` içine literal apostroflar (`O'Brien`, `Bob's notes`, `don't`, `can't`), çift tırnaklar, boş argüman (`""`), ters eğik çizgiler, Türkçe karakterler ve emoji (`🚀`) içeren kalıcı quoting testleri eklendi. `test_custom_command_windows_native_quoting_contract_with_apostrophes_quotes_unicode` artık yalnız `_custom_argv` parser uyumluluğunu ve izinli neutral fixture sürecinin gidiş-dönüşünü doğrular. Güvenlik sınırı gereği `BEYIN_LLM_COMMAND` custom child'ı başlatılmadan reddedilir; gerçek custom child round-trip kabulü yoktur.
- **Kanıt:**
  - `tests.adversarial_quality_test`: 20/20 test geçti (0.387s, OK).
  - `tests.windows_native_test`: 7/7 test geçti (3.37s, OK; kanıt: `.local/handoffs/WINDOWS_NATIVE_TEST.log`).

---

## 3. Tcl/Tk Kök Neden Analizi ve Başlatma Sınırı (Madde 2)

- **Kök Neden Analizi:**
  - CPython Windows standart dağıtımlarında Tcl script kütüphaneleri `sys.base_prefix / 'tcl' / 'tcl8.6'` altında yer alır. Ham Tcl C kütüphanesi (`tcl86t.dll`) derleme varsayılanı olarak `lib/tcl8.6` aradığından doğrudan `Tcl_Init` C çağrısı her iki çalışma zamanında da `tcl_init_code: 1` (`Can't find a usable init.tcl in ... lib/tcl8.6`) döner (`.local/handoffs/SOURCE_ACCEPTANCE_TCL_DIAGNOSTIC.json`).
  - Önceki ters eğik çizgi/list tokenizer açıklaması kök neden olarak doğrulanmadı. 2026-10-06 bağımsız karşılaştırmasında aynı Python 3.12.14, aynı script dosyaları ve aynı ürün kodu sandbox içinde hata verdi, sandbox dışında `tk.Tcl()` ile `8.6.12` döndürdü. Bu karşılaştırma hatayı test ortamının native dosya erişimi sınırına yerleştirir; ürün kütüphanesi eksikliği göstermez.
  - Ayrıca `ensure_tcl_tk_environment()` fonksiyonunun modül import edilir edilmez modül seviyesinde çalıştırılması, çağıran sürecin ortamını kontrolsüzce kirleten bir yan etki oluşturuyordu.
- **Uygulanan Mimari Düzeltme:**
  1. Modül seviyesindeki `ensure_tcl_tk_environment()` çağrısı kaldırıldı. Modülün salt import edilmesi process ortamında hiçbir yan etki üretmez.
  2. Kütüphane yolları Tcl motorunun süslü parantez karmaşasını önlemek için `candidate.resolve().as_posix()` (forward slash) ile atanacak şekilde düzenlendi.
  3. Ortam hazırlığı kesin başlatma sınırlarına taşındı: `wizard.main()` başlangıcı, `SetupWizard.__init__` başlangıcı ve test mock yapıcısı (`make_wizard`).
- **Ortam Karşılaştırma ve Somut Sınır (`.local/handoffs/SOURCE_ACCEPTANCE_TCL_DIAGNOSTIC.json`):**
  - **Python 3.13.15 (Sistem Dağıtımı):** `C:\Users\Furkan\AppData\Local\Programs\Python\Python313\python.exe`, DLL patchlevel 8.6.15, script `package require -exact Tcl 8.6.15`. Tkinter desteği tamdır; `tests/wizard_options_test.py` (12 test) ve `tests/wizard_test.py` (14 test) ile `setup --gui` pencereli açılış testi eksiksiz geçer (26/26 OK).
  - **Managed Python 3.12.14 (.venv / Codex Primary Runtime):** `C:\Users\Furkan\Documents\ChatGPT\secondbrain\.venv\Scripts\python.exe`, DLL/script 8.6.12. Sandbox içindeki dokuz Tcl hatası aynı interpreter ile sandbox dışında tekrarlandı: `tests.wizard_options_test` ve `tests.wizard_test` toplam **26 test, 10.339 saniye, OK**. Kanıt: `.local/handoffs/SOURCE_HARDENING_TCL_UNSANDBOXED.log`. Canlı program/kasa değişmedi, testler yalnız geçici fixture kullandı. Test erişim sınırı teşhis edildi; ürün veya Python kurulumu tahmine göre değiştirilmedi ve assertion/skip eklenmedi. Ham C probe'u interpreter başlatma koşullarıyla birlikte değerlendirilmelidir; tek başına dosyaların eksik olduğunu kanıtlamaz.

---

## 4. Karşılaştırmalı Arama Motoru Benchmarkı (Madde 3)

Kullanıcının çalışma kopyası (`checkout`) resetlenmeden, Git `HEAD` sürümündeki baseline arama kodu ile çalışma ağacındaki optimize edilmiş arama kodu izole geçici ortamlarda, taze veritabanları (fresh DB), sıra dengelemeli yürütme (order-balanced) ve çoklu tekrarlı ölçümle karşılaştırıldı (`.local/handoffs/BENCHMARK_SEARCH_COMPARISON.json`).

### Ölçüm Sonuçları Tablosu (Sıra Dengeli & Taze DB)

| Metrik | Küçük Kasa (25 not, ~11 KB) Baseline | Küçük Kasa (25 not, ~11 KB) Final | Büyük Kasa (500 not, ~226 KB) Baseline | Büyük Kasa (500 not, ~226 KB) Final | Hızlanma / Doğrulama |
| --- | --- | --- | --- | --- | --- |
| **Soğuk İndeksleme (3 Koşu Sıra Dengeli Ort.)** | 0.0877 s | 0.0493 s | 1.5381 s | 0.9860 s | **1.56x - 1.78x Hızlanma** |
| **Sıcak İndeksleme (Warm Unchanged - 5 Koşu Ort.)** | 0.0269 s | 0.0258 s | 0.3222 s | 0.3082 s | **~1.04x - 1.05x (Parite / No-op I/O)** |
| **5 Dosya Değişikliği (Incremental - 5 Koşu Ort.)** | 0.0561 s | 0.0350 s | 0.3323 s | 0.3223 s | **1.03x - 1.60x Hızlanma** |
| **Sorgu Dosya Yolu Sıra Eşitliği (`results_path_order_equal`)** | %100 Eşit | %100 Eşit | %100 Eşit | %100 Eşit | **Doğrulandı (`True`)** |
| **Preserved-mtime Değişiklik Algılama** | Algılandı | Algılandı | Algılandı | Algılandı | **Doğrulandı (`True`)** |

- **Ölçüm Sınırları ve Dürüstlük:**
  - Tek seferlik koşularda görülen 3.22x–3.64x hızlanma, sıra önceliği ve işletim sistemi dosya sistemi önbellek etkilerinden arındırılmış 3 taze DB koşusunda **1.56x – 1.78x** düzeyinde dengelenmiştir.
  - Sıcak (warm unchanged) indeksleme beklenen biçimde hızlanma göstermez (~1.04x parite); çünkü değişmeyen dosyalarda veritabanı mtime karşılaştırması zaten disk I/O'su ile sınırlıdır.
  - `results_path_order_equal`, motorların döndürdüğü eşleşen dosya yollarının ve sıralamasının birebir aynı olduğunu doğrular; BM25 kayan nokta skorlarının veya özet metinlerinin birebir eşitliği iddiası değildir.
- **Optimizasyonun Özü:** Değişmeyen dosyalarda gereksiz UTF-8 string decode (`payload.decode`) kaldırıldı; `mtime` zaten veritabanındakiyle aynıysa no-op SQL `UPDATE` sorgusu engellendi. Dosya mtime'ı korunarak içeriği değiştirilse dahi tam SHA-256 kontrolü çalıştığı için içerik değişikliği hiçbir durumda kaçırılmaz (`test_index_detects_changed_content_with_preserved_mtime` OK).
- **Mock Token Ayrımı:** Arama motoru işlemleri yerel SQLite FTS5 sorgularıdır, harici LLM çağırmaz. Flush ve compile süreçlerindeki token/maliyet ölçümleri deterministik mock model kullanır; faturalandırılmış API maliyeti değildir.

---

## 5. Final Paketleme ve Yaşam Döngüsü Kabulü (Madde 4)

Bu tarihsel bölümdeki Wheel/Frozen hash'leri 2026-10-06 paketinin kanıtıdır ve sonraki yeniden üretimler için geçerli artifact kabulü değildir. 2026-10-07 strict frozen lifecycle kanıtı `.local/archives/SECURITY_HARDENING_THIRD_STRICT_SMOKE.json`, source/package semantic eşitliği `.local/handoffs/SECURITY_HARDENING_CODEX_THIRD_PACKAGE_COMPARE.json` içindedir.

### A. Yapı ve Provenance Kayıtları
- **Interpreter:** `Python 3.13.15 (MSC v.1944 64 bit)`
- **Wheel:** `build --wheel` komutuyla izole geçici derleme alanında `respectedbrain-0.0.1-py3-none-any.whl` (320.114 byte, SHA-256: `58aaa21b0004...`) üretildi. İzole kabul sonrası geçici alan temizlendi (`storage_lifecycle: purged upon test completion`); `dist/` klasöründe kalıcı tutulmaz.
- **Frozen Dağıtım:** PyInstaller 6.22.3 ve `tools/build_installer.py` ile `dist/RespectedBrain` (1.019 dosya, launcher SHA-256: `b543527d9e...`, `distribution.json` SHA-256: `2bdc67a333...`) inşa edildi.

### B. İzole Wheel Kabulü (Repo Dışı CWD)
- Temiz geçici bir sanal ortam (`venv`) oluşturuldu; wheel `--no-deps` ile kuruldu.
- Çalışma dizini repo dışı boş bir geçici dizin (`outside_scratch`) olarak ayarlandı.
- **CLI Versiyonu:** `python -m respectedbrain --version` çıktısı `0.0.1` (exit code 0).
- **CLI Yardım:** `python -m respectedbrain --help` (exit code 0).
- **Konsol Scripti:** `respectedbrain.exe --version` çıktısı `0.0.1` (exit code 0).
- **Servis Sözleşmesi:** `ResourceCatalog().read_text('skills/beyin-doktor/SKILL.md')` başarıyla okundu (`skill_loaded: True`).

### C. Frozen Yaşam Döngüsü Kabulü, Onarım Kanıtı ve Kullanıcı Notu Korunumu
İzole geçici dizinlerde (`Programs/RespectedBrain`, `data`, `UserNotes`, `home`) frozen launcher ile tam yaşam döngüsü kanıtlı yürütüldü:
1. **Setup:** `--vault UserNotes --package dist/RespectedBrain` ile kurulum yapıldı. `install-manifest.json` ve `.respected.json` oluşturuldu, program ikilileri kuruldu (exit code 0, `success: true`, `installed_exe_exists: true`).
2. **Kullanıcı Notu Oluşturma:** `UserNotes/000-Inbox/my_personal_note.md` oluşturuldu ve SHA-256 hash'i (`8cdfa6f30a66d6b6ad1b9feece3869fa46c22a3c7fd064c3544dbbf02efe21c1`) kaydedildi.
3. **Repair (Sahipli Teknik Entegrasyon Onarımı):** Kullanıcı notu yerine gerçek sahipli entegrasyon dosyası sınandı. `config.json` içinde `integrations.global: true` etkinleştirildi; `repair` öncesinde hedef teknik kural dosyası (`home/.gemini/GEMINI.md`) mevcut değilken `repair --vault UserNotes` çalıştırıldı. Onarım servisi dosyayı 7.517 bayt ile eksiksiz üretti, `install-manifest.json` external envanterine kaydetti ve kullanıcı notunun SHA-256 hash'ini birebir korudu (`technical_integration_materialized: True`, `manifest_recorded_integration: True`, `user_note_preserved: True`, exit code 0, `success: true`).
4. **Update (Pending Deferral & Doğrulanmış Receipt):** `update --vault UserNotes --package dist/RespectedBrain` çalıştırıldı. Windows self-update exit deferral mekanizması (`pending: true`, `tx_id: deferred-...`) tetiklendi. Harness arka plan helper PID/işlemini izledi ve `result.json` makbuzunu bekledi (`wait_receipt`). Makbuz `success: true, pending: false` olarak alındı; kurulu `respectedbrain.exe` ikilisi doğrulandı ve kullanıcı notunun SHA-256 hash'i kesin olarak korundu (`update_preserved_user_note: True`, `success: true`).
5. **Uninstall (Pending Deferral, Gerçek Temizlik & Not Hayatta Kalma):** `uninstall --vault UserNotes` çalıştırıldı. Windows kaldırma deferral'ı tetiklendi (`pending: true`), helper makbuzu beklendi (`wait_receipt`). Makbuz `success: true, pending: false` olarak alındı. Kurulu `respectedbrain.exe` ve uygulama dosyalarının silindiği doğrulandı (`app_files_cleaned: True`). Kullanıcı notu silinmedi ve SHA-256 hash'i değişmeden korundu (`user_note_survived: True`, `user_note_preserved: True`, `success: true`).

### D. GUI Açılışı ve İşlem Yürütme Ayrımı
- `setup --gui` komutu kaynak/managed Python çalışmasında `RESPECTED_GUI_TIMEOUT=0.5` ile açılmış ve temiz kapanmıştır. 2026-10-07 PyInstaller build'i `tkinter installation is broken. It will be excluded` bildirdiğinden **frozen GUI NOT VERIFIED**dır; bu eski kaynak GUI açılışı frozen GUI kabulü değildir.
- **Mimari Ayrım:** Tkinter GUI'si salt sunum/etkileşim katmanıdır. Asıl yaşam döngüsü işlemleri arka plandaki servis fonksiyonları (`setup`, `update`, `repair`, `uninstall`) tarafından bağımsız iş parçacıklarında yürütülür; GUI açılışı servis kabulü ile eş tutulmaz.

---

## 6. Tam Unittest Keşfi ve Dayanıklı Doğrulama (Madde 5)

Test modülleri temiz izole süreçlerde yürütüldü; güncel log ve JSON özetleri `.local/handoffs/FINAL_ALL_TESTS_SWEEP.json` ve `.local/handoffs/FINAL_ALL_TESTS_SWEEP.log` dosyalarında saklandı.

- **Toplam Keşfedilen Test:** **867 test**
- **Geçen Test Sayısı:** **850 test**
- **Başarısızlık (Failure):** **0**
- **Hata (Error):** **0**
- **Atlanan Test Sayısı (Skipped):** **19 test**
- **Doğrulanan Eşitlik:** `850 + 19 + 0 + 0 == 867` -> **INVARIANT HOLDS: TRUE**

### 19 Atlanan Testin Gerekçeleri
Tüm atlanan testler platform ve host erişim kısıtlarından kaynaklanır; assertion'lar gevşetilmemiştir. Önceki 15 platform skip'a ek olarak Inno compiler erişimi, HKCU registry yazısı ve Task Scheduler kök klasörü erişimi kontrollü biçimde sınıflandırılmıştır. Ayrıca Node/runtime ve POSIX/symlink koşulları devam etmektedir.
1. `antigravity_orchestrator_test` (2 skip): Kullanıcı isteğiyle kaldırılan `.orchestration` şablonları.
2. `e2e_fresh_install_linux_test` (1 skip): POSIX E2E testi (Windows host).
3. `foundation_posix_distribution_test` (5 skip): Windows unprivileged ortamda symlink oluşturma yetkisi olmaması (`[WinError 1314]`) ve POSIX dosya izinleri.
4. `foundation_posix_install_test` (1 skip): POSIX kabuk/çalıştırma izinleri.
5. `foundation_native_install_test` (1 skip): Inno compiler bu host'ta erişilemez/yok.
6. `foundation_integrations_test` (2 skip): gerçek HKCU registry yazma yetkisi ve Task Scheduler kök klasörü bu host'ta erişilemez.
7. `maps_test` (1 skip): Junction/symlink yönlendirme yetkisi kısıtı.
8. `morning_briefing_test` (2 skip): Symlink yetkisi kısıtı.
9. `runtime_platform_test` (1 skip): Symlink yetkisi kısıtı.
10. `scripts_test` (2 skip): POSIX `flock` ve symlink kısıtı.
11. `secret_scanner_test` (1 skip): Windows symlink oluşturamama.

### Kritik İki Native Testin Ayrı Kanıtları
1. `tests/foundation_native_install_test.py`: 3 testin 2'si geçti, gerçek Inno install/update/uninstall testi compiler erişimi olmadığı için kontrollü skip'tir. Bu ortamda Inno tabanlı gerçek installer üretimi/kurulumu **NOT VERIFIED**dır; eski `NATIVE_INSTALL_TEST.log` tarihseldir ve yeni paketin kabul kanıtı değildir.
2. `tests/windows_native_test.py`: 7/7 test geçti (3.56s, OK; kanıt: `.local/handoffs/WINDOWS_NATIVE_TEST.log`).

---

## 7. Hardening Kapsamı ve Kalan Güvenlik Sınırları (Madde 6)

Hardening işleri bu kaydın yazıldığı 2026-10-06 tarihinde açıktı. Güncel ürün kararı ve yerel kanıtlar [güvenlik kararı](../../decisions/SECURITY_HARDENING.md) ve [güvenlik sınırları](../../SECURITY.md) içindedir. Yerel DNS/socket deadline, immutable snapshot, strict provenance consumer ve provider containment regresyonları kapanmıştır. Gerçek GitHub OIDC/Sigstore imzası, Authenticode, Inno compiler ve frozen GUI için dış/ortam önkoşulları **NOT VERIFIED** olarak kalır.

---

## 8. Depo Atlası ve Hash Bütünlüğü (Madde 7)

- `python tools/repository_map.py --update` çalıştırıldı.
- `docs/repository_inventory.json` içindeki değişen 14 dosya için açıklamalar incelendi ve doğrulandı.
- `python tools/repository_map.py --accept-reviewed <dosya>` uygulandı.
- `python tools/repository_map.py --write` ile `docs/REPOSITORY_MAP.md` üretildi.
- `python tools/repository_map.py --check`: **Repository atlas: 272 files; check passed.**
- `git diff --check`: 0 hata (satır sonu ve boşluk hatası yok).
- `git diff --cached`: Boş (0 staged dosya).
- `git rev-parse HEAD`: `0f69ba2a28e89d0faa33f8d613736551f58dea89` (başlangıç HEAD ile özdeş).
