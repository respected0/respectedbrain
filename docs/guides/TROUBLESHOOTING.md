# 🩺 Sorun Giderme

> Önce kullanılan kökü, UUID'yi ve hata kapsamını belirleyin. Notları sıfırlamak veya tekrar template kopyalamak tanı yöntemi değildir.

## 1. İlk kontrol

```text
respectedbrain --version
respectedbrain vault list
respectedbrain configure
```

Module/console/native komutu aynı kaynak/kurulum değildir. Doğru executable'ı kullandığınızı ve `RESPECTED_APP_DIR`, `RESPECTED_DATA_DIR`, `RESPECTED_VAULT_PATH` override'larını kontrol edin. Config çıktısında yerel yollar bulunabilir; dışarı paylaşırken kişisel alanları çıkarın.

## 2. Belirti → kontrol

| Belirti | Önce bakılacak |
| --- | --- |
| Kasa bulunamadı / UUID conflict | Marker, registry path, açık selector; [CONFIGURATION](CONFIGURATION.md) |
| Dolu hedef kurulamıyor | Boş yeni hedef, kayıtlı modern kasa veya migration; bilinmeyen hedefi zorlamayın |
| Daily yazılmıyor | İlgili hook etkin/güvenilmiş mi, doğru profile/CLI login mi, transkript/session ve DataRoot logları |
| Auto fallback beklenenden farklı | Genel auto ile açık preferred davranışı; [MULTI_AI](MULTI_AI.md) |
| Sabah brifingi yok | Schedule desired-state/OS görevi, yerel saat, günlük başarı receipt'i, CLI kota/ağ |
| Arama eski sonuç veriyor | Doğru UUID ve `search --reindex`; indeks yazımı teknik cache'e gider |
| MCP bozuk JSON | Stdio stdout'ına tanı yazılmaması, editör kayıt komutu, UUID/launcher doğruluğu |
| GUI seçimi yanlış | Açık flag ile kayıtlı default ayrımı, seçili kasa settings, package yolu |
| Pending update/uninstall | Son receipt; parent process çıkışı ve helper başarısı |
| Rollback conflict | İşlemden sonra değişmiş dosya; journal/hash/yedek korunmalı |
| Panel açılamıyor | Loopback port çakışması, doğru UUID, sunucu komutu hâlâ çalışıyor mu |

## 3. Sağlık araçları

`beyin-doktor` paket skill'i ajan tarafından uygulanabilen talimat setidir; native programda `respectedbrain doctor` adlı komut yoktur. Not denetimleri dispatcher üzerinden yapılabilir:

```text
respectedbrain maintenance --vault-id <UUID> vault_linter --help
respectedbrain maintenance --vault-id <UUID> architect_scan --help
respectedbrain maintenance --vault-id <UUID> tiling_check --help
```

`--help` araç parser'ını gösterir; üst CLI seçili kasa context'i isteyebilir. Onarım/merge/ingestion araçları yazabilir; bütün maintenance komutları salt okunur değildir. [Komut kataloğu](../development/CLI.md).

## 4. Güncelleme arızası

DataRoot `backups/<tx_id>` ve `logs/` alanını, sonuç `conflicts/pending/tx_id` değerlerini birlikte değerlendirin. `recover` yarım işlemleri hash karşılaştırmasıyla ele alır. Recovery güvenliği için değişmiş dosyayı zorla eski yedeğe döndürmez. Kaynağı/unknown dosyayı silerek veya legacy uninstaller çalıştırarak conflict'i aşmayın; [UPDATE](UPDATE.md).

## 5. Hata raporunda ne bulunmalı?

OS, Python veya native sürüm, komutun kişisel alanlardan temizlenmiş biçimi, kullanılan kök/UUID seçimi, işlem kimliği, exit code ve sınırlı hata etiketi yeterli başlangıçtır. Ham transkript, provider stdout, credentials ve bütün config'i public issue'ya yapıştırmayın. Gerçek bir koşuyu doğrulamadan “bu platform test edildi” yazmayın.
