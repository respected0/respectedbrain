# Kurulum

[Klasörler ve SSS](../../README.md), [yetkili mimari](../superpowers/specs/2026-10-03-modular-foundation-design.md).

Native paketi hedef işletim sistemi üzerinde üretin veya o platform için üretilmiş dağıtımı kullanın. Kaynak geliştirme Python 3.10+ gerektirir; kurulu native program kendi çalışma ortamını içerir.

Windows kurucusunda program dizini ve kasa ayrı seçilir. Global/MCP/zamanlayıcı/kısayol yeni kurulumda kapalıdır; tekrar kurulum kapalı tercihleri açmaz. Yerel AI CLI yalnız AI özetleme işlemleri için gerekir.

```text
respectedbrain setup --vault "<not kasası>" --package "<doğrulanmış dağıtım>"
respectedbrain vault list
respectedbrain maps
respectedbrain search --json "aranan kelime"
respectedbrain configure --summary-provider codex
```

`RESPECTED_APP_DIR` ve `RESPECTED_DATA_DIR` mutlak, birbirinden ve kasadan ayrı dizinlerle kurulum köklerini değiştirir. Kasa `--vault` veya `--vault-id` ile seçilir; hatalı açık seçim başka kasaya sessiz geçmez.

Linux AppRoot `~/.local/lib/respectedbrain`, DataRoot `$XDG_DATA_HOME/respectedbrain` (yoksa `~/.local/share/respectedbrain`). macOS AppRoot `~/Applications/RespectedBrain.app`, DataRoot `~/Library/Application Support/RespectedBrain`. Native doğrulama ilgili host/CI üzerinde yapılır.

Mevcut dolu kasaya fresh template uygulanmaz; önce [migration önizlemesi](UPDATE.md) yapılır. Kasa kaydı motor kurulumunun yerine geçmez.
