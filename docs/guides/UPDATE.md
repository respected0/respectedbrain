# Güncelleme ve migration

`respectedbrain update --package "<yeni dağıtım>"` doğrulanmış native paketle programı günceller; kasa kimliği ve tercihleri korur. Windows'ta pending sonuç son makbuz beklenmeden tamamlandı sayılmaz.

Eski düzen için salt okunur plan:

```text
respectedbrain migrate --legacy-root "<eski kök>" --vault "<mevcut kasa>"
```

Plan kaynak/hedef/hash/sahiplik ve korunacak dosyaları gösterir; config/state/log/backup oluşturmaz. Conflict varsa geçiş yapılmaz. İsim veya .py uzantısı sahiplik kanıtı değildir.

Doğrulanmış plan/paketle `migrate ... --package "<yeni dağıtım>" --apply` değişiklik yapar. Hash'ler kilit alındıktan sonra tekrar doğrulanır. Kişisel overrides, notlar, .obsidian ve Templates korunur. Eski uninstaller çalıştırılmaz.

DataRoot/backups/<işlem>/ journal ve byte yedekleri değişiklikleri izler. Hata otomatik geri alır. Yarım işlemler `respectedbrain recover` ile hash kontrolü üzerinden kurtarılır; sonradan değişmiş kullanıcı dosyası zorla geri çevrilmez. `repair` sahipli program/bağlantı alanlarını onarır.

Eski kökle yeni AppRoot aynı seçilmez. Aktif yazıcılar tamamlandıktan sonra kilit alınır; kilit conflict'i zorla aşılmaz.
