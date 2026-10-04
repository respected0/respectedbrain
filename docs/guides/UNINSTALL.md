# Kaldırma

Windows uygulamalar listesindeki kaldırıcı veya `respectedbrain uninstall` ortak servisi çağırır. Yalnız hash'i hâlâ sahiplik kaydıyla eşleşen program dosyaları ve yönetilen bağlantılar kaldırılır. Kullanıcı değiştirmişse conflict raporlanır; dosya korunur.

Not kasası hedef değildir: daily, knowledge, Companion, projeler, Templates ve .obsidian kalır. DataRoot ayar/kayıt/yedekleri de varsayılan olarak kalır. `--purge-data` yalnız sahipli teknik dosyaları hedefler; bilinmeyen dosya ve yedek journal'ları korunur.

Eski kasaya konmuş unins000.exe ile migration yapmayın; geniş temizleme davranışı olabilir. [Migration önizlemesini](UPDATE.md) kullanın. Windows programından kaldırma pending ise son helper makbuzu henüz beklenmektedir. İşlem/conflict sonucu DataRoot günlüklerinde bulunur.
