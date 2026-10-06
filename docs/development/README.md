# 🛠️ Geliştirici Rehberi

> Kaynak geliştirme, native paket üretimi ve canlı kurulum farklı işlemlerdir. Dosya dosya navigasyon [atlasta](../REPOSITORY_MAP.md), ürün sözleşmesi [SPECIFICATION](../SPECIFICATION.md).

## 1. Geliştirme ortamı

```text
# Sanal ortamı oluşturun:
python -m venv .venv

# Windows (.venv çalıştırıcısı ile):
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\python.exe -m respectedbrain --version

# macOS / Linux (.venv çalıştırıcısı ile):
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m respectedbrain --version
```

Komutları küresel Python yerine mutlaka seçili venv interpreter'ıyla çalıştırın. Paket Python >=3.10 ister; setuptools/wheel/build/PyInstaller dev gereksinimleridir. Paket sürümünün kaynağı `pyproject.toml`, elle kopyalanmış sürüm damgası değildir. Editable kurulum checkout'a bağlanır; checkout/worktree silmeden bağlantıyı ana kaynağa yönlendirin veya yeniden kurun. Aktif geliştirme için ana `.venv` yeterlidir; ZIP'teki eski izole test ortamları çalışır ortam olarak sunulmaz.

Aşağıdaki geliştirme komutlarında Windows çalıştırıcısı `.venv/Scripts/python.exe` kullanılır. macOS/Linux'ta aynı konuma `.venv/bin/python` yazın; native build için platform ve dağıtım hedefini de kendi işletim sisteminize göre seçin.

## 2. Kod okumaya nereden başlarım?

`pyproject.toml → __main__.py → cli.py → bootstrap.py → core/context.py` giriş akışıdır. Core saf roots/config/context sunar; feature module CLI import etmez. Kaynak `src/respectedbrain`, paket tarifleri `packaging`, araçlar `tools`, testler `tests` altındadır. Sorumlulukların ayrıntısı [ARCHITECTURE](../ARCHITECTURE.md).

## 3. Native build

```text
.venv/Scripts/python.exe tools/build_installer.py --platform windows --output dist
.venv/Scripts/python.exe tools/verify_distribution.py --platform windows --distribution dist/RespectedBrain
```

macOS: `--platform macos`, `dist/RespectedBrain.app`. Linux: `--platform linux`, `dist/RespectedBrain`. Build ilgili OS üzerinde yapılır; Windows installer için Inno compiler gerekir. Build `--no-installer` ile yalnız native payload üretebilir. `distribution.json` hash doğrulaması yayıncı imzası değildir. OS yayın kabukları/DMG/makeself tarifleri workflow'da ayrı kapılardır.

`.venv`, `__pycache__`, `build`, `dist`, egg-info üretim/ortam dosyalarıdır. `.local/archives` kurtarılabilir yerel kanıttır; Git/atlas kapsamı dışındadır. Bu dosyalar kullanıcı not kasası değildir. Test/bundle build'i build/dist'i yeniden oluşturabilir.

## 4. Doğrulama

```text
.venv/Scripts/python.exe -m unittest discover -s tests -p '*test*.py'
.venv/Scripts/python.exe tests/run_all.py --python-only
.venv/Scripts/python.exe tools/repository_map.py --check
git diff --check
```

Tam suite native paket isteyen testler içerir; artifact yokken yerel kısa koşuya “tüm ürün geçti” demeyin. Dar doğrulamada etkilenen anlamlı modülleri seçin; fiziksel paket smoke/Windows kabul/shell kapıları ayrı komutlardır. [Test matrisi](../TEST-MATRIX.md) host/sürüm/skip kapsamını ayırır. Yazılmamış platform sonucu üretmeyin.

## 5. Atlası aynı görevde güncelle

```text
.venv/Scripts/python.exe tools/repository_map.py --update
# Yeni/değişen rol, amaç ve ilişkileri JSON'da gerçek içerikle açıklayın.
.venv/Scripts/python.exe tools/repository_map.py --accept-reviewed path/to/changed.py
.venv/Scripts/python.exe tools/repository_map.py --write
.venv/Scripts/python.exe tools/repository_map.py --check
```

Markdown elle düzenlenmez. İnceleme hash'i açıklamanın matematiksel doğruluğunu kanıtlamaz; okuyup anlamlandırmak geliştiricinin işidir. Staged deletion envanterden çıkar; yalnız diskten silinmiş tracked file hata sayılır. Generated JSON/Markdown kendi kendini hash'leme döngüsünü önler.

## 6. Yayın ve canlı veri

Kaynak push, CI artifact ve release tag farklıdır. `.github/workflows/release.yml` sürüm/tag, build, verify, tests ve host smoke kapılarını tanımlar; kurulmuş imza/notarization varsayılmaz. Bu projede push sonrası sonuç sürekli poll edilmez; kullanıcı sonuç çıktığında yeniden çağırır. Aktif kararlar [PROJECT_STATUS](../PROJECT_STATUS.md).

Testler geçici kasa/OS kayıtlarıyla çalışmalıdır. Kaynak düzenlemesini canlı AppData kurulumuna veya kişisel kasaya otomatik uygulamayın. Legacy okuma kodu eski kurulumlar için kullanılır; isimlerinin geçmesi ölü kaynak kanıtı değildir.
