# Çoklu AI bağlantıları

Talimat/skills kaynağı paket resources alanıdır. Beş sağlayıcının kural/hook ayarları aynı bağlamdan üretilir. Kişisel değişiklikler UUID'ye bağlı DataRoot overrides alanında yaşar.

Kurulum seçenekleri `--global`, `--mcp`, `--schedule`, `--shortcut`; kapatma seçenekleri `--no-global`, `--no-mcp`, `--no-schedule`, `--no-shortcut` olur. Belirtilmeyen seçenek kayıtlı tercihi korur; yeni kurulumda tamamı kapalıdır.

Global bağlantı diğer kod projelerinde de kasayı kullanır. MCP ayrı opt-in'dir. Mevcut sağlayıcı ayarları ve diğer MCP sunucuları korunur. Kullanıcı değiştirmiş yönetilen alan conflict olarak raporlanır. Önceki Codex notify zinciri korunur.

Native Windows için `windows-native` varsayılan profildir; WSL otomatik bağımlılık değildir. Açık `windows-wsl` profilinde Linux native launcher ve Linux ortamında aynı taşınabilir UUID'ye ait kasa kaydı gerekir. Bu doğrulanmadan köprü kurulamaz. Windows config'i Linux'a ortak ayar dosyası olarak verilmez.

Özetleyici auto veya kurulu sağlayıcı olabilir. Mevcut summary_provider/sıra/fallback tercihleri korunur. Sağlayıcı oturumu ve kotası AI işlemlerini etkiler.
