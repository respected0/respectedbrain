# Respected Brain 1.4.0 upstream uyarlama backlog'u

Bu dosya 2026-09-01 ve 2026-09-02 tarihlerinde bütün dallarıyla incelenen
`avenoxai/avenoxbeyin` ve forklarından Respected Brain'e uyarlanması planlanan işleri kalıcı
olarak kaydeder. Buradaki dokuz maddenin ürün kapsamı kullanıcı tarafından onaylanmıştır; maddeler
**henüz uygulanmış değildir**. `1.3.0` Respected Brain tam yeniden adlandırma/migration sürümüdür;
bu backlog onun ardından `1.4.0` olarak uygulanacaktır.

Doğrudan cherry-pick yapılmayacak. Her davranış Claude, Codex, Cursor ve Antigravity ile çalışan
ortak runtime'a; Windows native, WSL, Linux ve macOS hedeflerine uyarlanacaktır.

## Planlanan kapsam: dokuz madde

### 1. Modern Codex transcript desteği

- Kaynak: `banadabi/fix/flush-summary-normalization-codex-items-20260831` (`857351e`).
- `event_msg/item_completed` olaylarındaki `UserMessage` ve `AgentMessage` öğeleri ile büyük/küçük
  harf farkı taşıyan `Text` alanları normalize edilecek.
- Mevcut eski Codex, Claude, Cursor ve Antigravity transcript davranışları gerilemeyecek.

### 2. Güvenli model çıktısı normalizasyonu ve tek şema retry'ı

- Kaynak: aynı Banadabi dalı (`857351e`).
- Modelin şema öncesinde ürettiği güvenli açıklama/preamble ayıklanacak.
- Çıktı şemaya uymuyorsa provider-neutral `_run_model` zinciriyle en fazla bir düzeltme denemesi
  yapılacak; sonsuz veya sağlayıcıya özel retry olmayacak.
- Ham transcript'in prompta sınırsız eklenmesi gibi veri sızıntısı ve boyut riskleri alınmayacak.

### 3. Upgrade sırasında tracked Python bytecode temizliği

- Kaynak: `banadabi/fix/upgrade-untrack-pycache` (`f922558`).
- Eski vault'ların `.gitignore` dosyasına `__pycache__/` ve `*.pyc` kuralları transaction içinde
  eklenecek.
- Git tarafından daha önce izlenmiş bytecode index'ten çıkarılacak, diskteki kullanıcı dosyaları
  silinmeyecek.
- Dosya adları güvenli biçimde işlenecek; hata sessizce yutulmayacak ve işlem fail-closed olacak.

### 4. Eksik platform ve sınır regresyonları

- Kaynaklar: `morp1e/main` (`d39319d`) ve `Ahmet53535353/main` (`f028135`).
- Sistem geçici dizini vault içine yönlendirilirse compiler'ın model çağrısından önce reddettiği
  kanıtlanacak.
- `pyenv` shim'i kullanan sahte `PATH` upgrade fixture'ının gerçek Python yorumlayıcısına güvenli
  çözülmesi test edilecek.
- WSL'den çağrılan `schtasks.exe` çıktısı Türkçe OEM code page (`cp857`) kullandığında scheduler
  kurucusu UTF-8 varsayımıyla çökmeyecek; mevcut görev sorgusu, yedekleme ve apply yolu gerçek
  Windows'ta regresyon testine bağlanacak.
- WSL ile Windows yol eşleme ve native PowerShell davranışı gerçek platform kapılarında korunacak.

### 5. Transactional sürüm, kurulum ve belge geçişi

- Hedef sürüm `1.4.0` olacak; yeniden adlandırılmış `1.3.0` vault'lar transactionally
  yükseltilecek.
- Tek kaynaklı rules/skills üretimi, symlink kullanmama ilkesi ve provider fallback zinciri
  korunacak.
- README, setup, teknik belgeler, sürüm damgaları ve fresh/upgrade testleri aynı değişiklik setinde
  güncellenecek.

### 6. Provider-neutral immutable handoff event log

- Fikir kaynağı: `enesadakli/windows-native` (`920b597`). Fork uygulaması doğrudan alınmayacak.
- Claude, Codex, Cursor, Antigravity ve sistem olayları için create-only, doğrulanan JSON olay
  dosyaları kanonik kayıt olacak.
- `Last-Session.md` ve `Threads.md` bu olaylardan atomik üretilen, insan tarafından okunabilir
  projection'lar olacak; `Core.md` insan tarafından yönetilen kimlik kaynağı olarak kalacak.
- Çakışma eski olayı ezmeyecek: bekleyen karar olarak gösterilecek, çözüm yeni bir olay olarak
  kaydedilecek.
- SessionStart yalnız kompakt indeks/projection okuyacak; bütün vault'u taramayacak.
- Mevcut kişiselleştirilmiş Last-Session ve Threads içeriği ilk migration event'ine kayıpsız
  aktarılmadan dosyalar dönüştürülmeyecek.

### 7. Opt-in, doğrulanmış Restic yedekleme ve geri yükleme

- Fikir kaynağı: Enes forkundaki Restic/DPAPI çalışmaları (`e41c829`, `fa07b8e`, `e54322b` ve
  devamındaki ilgili commitler). Kullanıcıya veya Windows'a sabit kod doğrudan alınmayacak.
- Restic ön koşulu açıkça denetlenecek; araç sessizce kurulmayacak.
- Repository ve kimlik bilgileri vault dışında olacak. Windows'ta DPAPI, macOS'ta Keychain;
  WSL/Linux'ta açık onay ve uyarıyla vault-dışı `0600` credential dosyası kullanılacak.
- Zamanlama önce önizlenecek, yalnız açık onayla uygulanacak; kaçırılan çalışma davranışı platforma
  uygun olacak.
- İlk yedek ancak geçici dizine gerçek restore ve hash doğrulaması geçerse başarılı sayılacak.
- Varsayılan akış otomatik prune/silme yapmayacak; güvensiz kök, symlink ve reparse-point hedefleri
  fail-closed reddedilecek.

### 8. Opt-in private Git snapshot publisher

- Fikir kaynağı: `Ahmet53535353/main` saatlik Git backup commit'i (`21df5e2`). Fork kodu doğrudan
  alınmayacak.
- Özellik varsayılan olarak kapalı olacak; remote, branch, dahil/haricî yollar ve çalışma aralığı
  önizlenip açık kullanıcı onayıyla etkinleştirilecek.
- SessionEnd içindeki sağlayıcıya özel shell kopyaları yerine ortak lifecycle yalnız kilitli,
  detached ve provider-neutral bir `--if-due` worker tetikleyecek.
- Worker otomatik `pull` veya merge yapmayacak. Önce `fetch` ile divergence kontrol edecek;
  fast-forward olmayan veya detached HEAD durumunda hiçbir kullanıcı dosyasını değiştirmeden
  duracak.
- `git add -A` öncesi secret/forbidden-path kapısı ve tracked-secret kontrolü çalışacak. Commit ancak
  güvenli staged manifest için üretilecek.
- Başarı damgası yalnız commit uzak branch'te gerçekten görüldükten sonra atomik yazılacak; push
  hatası sessizce yutulmayacak ve sonraki denemeyi bir saat engellemeyecek.
- Restic'in yerini almayacak: Restic şifreli tam felaket kurtarma, Git publisher ise seçili metin
  dosyaları için okunabilir sürüm geçmişi ve isteğe bağlı off-site kopyadır.

### 9. Linux CI ve provider-neutral fresh-install E2E

- Fikir kaynakları: `Ahmet53535353/main` Linux CI ve temiz kurulum commitleri (`ee61527`,
  `bfb76b4`, `5213c69`). Fork testi doğrudan alınmayacak.
- `ubuntu-latest` workflow en az `permissions: contents: read` ile shell parse, Python testleri,
  upgrade transaction ve gerçek fresh-install lifecycle kapılarını çalıştıracak.
- E2E, SETUP adımlarını bağımsız bir ikinci implementasyon olarak elle kopyalamayacak; repository'nin
  canonical template/render/installer yollarını kullanacak.
- Claude-only stub ve sabit provider yerine ortak model runner üzerinden seçilebilir CLI stub'ları
  ile Claude, Codex, Cursor ve Antigravity girişlerinin aynı lifecycle'a ulaştığını kanıtlayacak.
- Test izolasyonu `$HOME` gibi üst süreç ortamını değiştirmeyecek; her subprocess için ayrı geçici
  home/git config kullanacak ve doğru `1.4.0` damgasını doğrulayacak.

## Uygulama sırası

1. **Güvenilirlik katmanı:** 1–4 için önce başarısız testler, sonra en küçük runtime/updater
   değişiklikleri.
2. **Hafıza sürekliliği:** event sözleşmesi, migration ve projection'lar için ayrı tasarım onayı;
   ardından 6. madde.
3. **Kalite kapısı:** 9. madde güvenilirlik katmanıyla birlikte kurularak sonraki değişikliklerin
   Linux release kapısı olur.
4. **Veri koruma:** ayrı tehdit modeli ve platform tasarımından sonra opt-in 7 ve 8. maddeler.
5. **Yayın:** 5. madde bütün katmanların fresh install, upgrade ve belge kapısıdır.

## Kabul kapıları

- Her davranış önce başarısız regresyon testiyle görünür olacak.
- Claude, Codex, Cursor ve Antigravity uyumluluğu korunacak; tek sağlayıcı zorunlu olmayacak.
- Windows native ve WSL gerçek ortamda; Linux/macOS uygun CI veya platform testiyle doğrulanacak.
- Kullanıcı verisi açık onay olmadan silinmeyecek, taşınmayacak veya yeniden yazılmayacak.
- Üretim değişikliği, commit ve push ayrı kullanıcı onayı olmadan yapılmayacak.

## Bilinçli olarak doğrudan alınmayanlar

- Sağlayıcı başına kopyalanmış lifecycle motorları ve Claude-only `_run_claude` yolları.
- Markdown içine gömülü, kırılgan event marker biçimi.
- Kişiye/Windows'a sabitlenmiş yedek hedefleri ve kimlik bilgileri.
- Ham linked-note gövdelerinin otomatik prompt enjeksiyonu.
- GSD test harness gürültüsü, billing/auth politikaları ve kişi-özel vault notları.
