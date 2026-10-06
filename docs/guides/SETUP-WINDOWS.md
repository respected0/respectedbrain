# 🪟 Windows Native Kurulumu

> WSL/Bash gerekmeden çalışan paket kurulumu. Genel akış [SETUP](SETUP.md), yerleşim [mimari](../ARCHITECTURE.md).

## 1. Tam olarak ne nereye kurulur?

```text
%LOCALAPPDATA%/Programs/RespectedBrain/
├── respectedbrain.exe
├── app/                         Paket, runtime bağımlılıkları ve resources
└── uninstall/                   Windows kaldırıcı araçları

%LOCALAPPDATA%/RespectedBrain/
├── config.json
├── install-manifest.json
├── logs/
├── backups/
└── vaults/<UUID>/
    ├── state/
    ├── cache/
    └── overrides/
```

Not kasası bunlardan ayrıdır; örneğin `C:/Users/<kullanıcı>/Documents/BenimBeynim`. Windows Documents yönlendirilmiş olabilir. Native program runtime'ı paketle gelir; DataRoot'a ayrı `runtime/` veya `scripts/` motoru kurulmaz.

## 2. Kurucu penceresi

`RespectedBrain-Windows-Setup.exe` program ve kasa yollarını ayrı alır. Program klasörünü mevcut not kasasına eşitlemeyin. Ortak kurulum hizmeti payload hash'lerini/sahipliği doğrular; Inno kabuğu Windows kayıt ve kaldırıcı görevlerini tamamlar. Programı ayrıca kaynak repodan eski `setup.py` ile kurma yolu yoktur.

Inno penceresi program ve kasa dizinlerini toplar; kişisel ad/provider ve dört bağlantı için ayrı checkbox sayfası içermez. Bu alanlar ortak Python wizard'ında (`setup --gui`) veya CLI seçenekleriyle düzenlenir. Inno deploy kayıtlı tercihleri kullanır; yeni defaults global/MCP/schedule/shortcut kapalıdır. Mevcut tercihler ve açık kapalı seçimler korunur. Kullanıcı profilini Native Windows ve WSL arasında karıştırmayın; [MULTI_AI](MULTI_AI.md) sınırları açıklar.

## 3. Silent kurulum

Kurucu silent arayüzünde `/DIR="<program yolu>"` ve `/VAULT="<kasa yolu>"` ayrı parametrelerdir; `/DATA="<teknik veri yolu>"` DataRoot seçer. Ortak CLI GUI'sinde `setup --gui --vault ... --package ...` kullanılır. Bunlar farklı arayüzlerdir; Inno seçeneklerini Python CLI argümanı sanmayın. Kesin shell seçenekleri `packaging/windows/respected_setup.iss` içinde tanımlıdır.

## 4. Kullanımda executable ve son makbuz

Frozen launcher kendi çalışan dosyasını yerinde değiştirmek/silmek için Windows exit sonrası helper kullanabilir. `pending` sonuç son başarı değildir. Çıktıdaki `tx_id` ile son makbuz yolunu çözün; deferred sonuç DataRoot `backups/deferred-<kimlik>/result.json` altında yazılır. Bazı işlemlerde CLI exit 0 kuyruğa alma başarısını gösterir; receipt/health doğrulaması ayrıca gerekir.

Kurulum sonrasında [ilk çalıştırma](BOOTSTRAP.md), [güncelleme](UPDATE.md), [kaldırma](UNINSTALL.md) rehberlerine geçin. Bilinmeyen dosya/çakışma varsa eski kaldırıcıyı çalıştırarak zorlamayın.
