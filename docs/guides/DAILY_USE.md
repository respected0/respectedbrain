# 📒 Günlük Kullanım

> Kurulum tamamlandıktan sonra konuşma, not, arama ve brifing akışı. Başlangıç için [BOOTSTRAP](BOOTSTRAP.md); ajan bağlantısı için [MULTI_AI](MULTI_AI.md).

## 1. Kasada ne nereye yazılır?

| Alan | İş |
| --- | --- |
| 📥 000-Inbox/Dump | Ham not ve hızlı yakalama |
| 🎯 100-Command-Center | Dashboard, haritalar, Briefings |
| 🏰 300-Projects | Proje notları |
| 🧠 500-Knowledge | İnsanların yazdığı kalıcı bilgi |
| 🛠️ 600-Arsenal | Araç/kaynak notları |
| 🔮 850-Companion | Core, Kurallar, Threads, Last-Session, Journal ve ilişkisel hafıza |
| daily | Makine oturum özetleri; insan notları yönetilen bloklardan ayrı tutulur |
| knowledge | Derlenmiş index, concepts, connections ve log |
| 📋 Templates / 📦 900-Archive | Yeni not şablonları / tamamlanan notlar |

Dosya adları template sözleşmesidir; AI ortağının görünen adıyla Companion dizinini gelişigüzel yeniden adlandırmayın. Daily derlemesi otomatik olabilir; ilişkisel notların anlamını kontrol etmek ve yanlış özeti düzeltmek hâlâ insan/ajan işidir.

## 2. Not arama ve harita

```text
respectedbrain search --vault-id <UUID> --json "transaction rollback"
respectedbrain search --vault-id <UUID> --reindex
respectedbrain maps --vault-id <UUID>
```

Search FTS5/BM25 tam metin motorudur; `--limit` ve `--category` filtreleri vardır. Sorgusuz kullanım indeks istatistiklerini gösterir. Search/--reindex teknik cache yazabilir; maps kasa haritalarını üretir. Embedding modeli zorunlu değildir ve mevcut arama otomatik anlamsal embedding sistemi diye sunulmaz.

## 3. Derleme ve sabah brifingi

```text
respectedbrain compile --vault-id <UUID> --dry-run
respectedbrain compile --vault-id <UUID> --before-date 2026-10-05
respectedbrain briefing --vault-id <UUID>
```

`--dry-run` derleme önizlemesidir; ancak kilit ve sağlık durumu gibi teknik I/O yapabilir, sistemde sıfır I/O garantisi değildir. Normal `compile`, `--before-date` verilmezse günün henüz devam eden günlüğünü de derlemeye dahil edebilir. Günün yarım kalmış notlarını hariç tutmak için açıkça `--before-date YYYY-MM-DD` seçeneği verilmelidir (oturum kapanışındaki otomatik `compile_catch_up` dünü ve öncesini süzmek için `before_date=now.date()` kullanır).

`briefing` zamanı gelmiş günlük sabah pipeline'ını çalıştırır. Sabah brifingindeki iç derleme filtresizdir; bu komut `--before-date` seçeneğini desteklemez. Derleme başarısız olsa bile geçerli bir brifing belgesi üretilip komut `exit 1` dönebilir. Sonraki çağrı aynı günün brifing dosyasını bulursa derlemeyi yeniden denemeden atlar; bu nedenle dosyanın bulunması tüm sürecin hatasız bittiğinin kanıtı sayılmaz. Schedule kurulmuşsa işletim sistemi zamanlayıcısı çalıştırır; kapalıysa bilgisayar kendiliğinden arka plan görevi açmaz. Metinler model çıktısıdır; kararlarınızı doğru yansıttığını kontrol edin.

## 4. Yerel kontrol paneli

```text
respectedbrain dashboard --vault-id <UUID> --port 8520 --open
```

Sunucu `127.0.0.1` loopback'e bağlanır; komut sunucu açıkken çalışmaya devam eder. Panel HTTP/JSON API ve UI'dır; kullanıcı hesaplı internet servisi olarak tasarlanmamıştır. Kaynakta permissive CORS vardır, bağımsız auth/CSRF güvenliği varsayılmaz. Portu internetten paylaşmak günlük kullanım yolu değildir; [SECURITY](../SECURITY.md).

## 5. Bakım ve kod işçisi

Bakım dispatcher'ı `maintenance <araç>` üzerinden çalışır. Linter/architect_scan/tiling_check ile onarım/merge/ingestion/yayın araçları aynı yan etki sınıfında değildir. Tüm mevcut isim/komutlar [CLI kataloğunda](../development/CLI.md); dosya işleri [atlasta](../REPOSITORY_MAP.md).

Orchestration hafıza kasasının içine kod koymaz; `--project-root` ile açık kod projesi alır. Worker izin/sandbox sınırları sağlayıcıya bağlıdır. Kullanıcı kod kapsamı ve acceptance geçmeden ana projeye apply yapılması güvence diye varsayılmaz. Bu rehber yeni AI modellerinin hesabını otomatik açmaz.

## SSS

**Kota biterse?** Fallback koşulları ve genel auto davranışı [MULTI_AI](MULTI_AI.md) içinde. Başka hazır CLI yoksa işlem başarısız olabilir.

**Özet yazılmazsa notlarım silinir mi?** Flush başarısızlığı önceki notları yeniden template'leme gerekçesi değildir. Hook/CLI/log/UUID kontrolüyle [sorun giderin](TROUBLESHOOTING.md).
