# Respected Brain — çoklu AI kullanımı

Bu dalda vault tek bir AI aracına ait değildir. Claude Code, Codex, Cursor ve Antigravity aynı
Markdown hafızasını, kuralları, skill'leri ve günlük/knowledge hattını paylaşır.

Kurulu platform profili tam olarak üç değerden biridir: macOS/Linux için `portable`, Windows
uygulamaları ile WSL motoru için `windows-wsl`, WSL/Bash olmadan Windows Python için
`windows-native`. Native sıfırdan kurulum [SETUP-WINDOWS.md](SETUP-WINDOWS.md) ile yapılır.
Damgalı `2.0.0` / `1.0.0`, `1.1.0` veya `1.2.0` Respected Brain vault'u native güncellenebilir;
damgasız v1'in native dönüşümü
henüz desteklenmez ve doğrulanmış WSL upgrade akışını kullanır.

## Tek kaynak ilkesi

Elle düzenlenecek ana dosyalar şunlardır:

- `.beyin/instructions.md`: ortak ajan talimatları
- `.beyin/skills/*/SKILL.md`: ortak skill'ler

Araçlara özel dosyalar üretilir; elle düzenlenmez:

- `CLAUDE.md` — Claude Code
- `AGENTS.md` ve `.codex/hooks.json` — Codex
- `.cursor/rules/beyin.mdc` ve `.cursor/hooks.json` — Cursor
- `.agents/rules/beyin.md`, `.agents/skills/` ve `.agents/hooks.json` — Antigravity
- `.claude/skills/` — Claude Code

Kaynaktan tekrar üretmek ve drift kontrolü yapmak için:

```bash
python3 scripts/render_integrations.py
python3 scripts/render_integrations.py --check
```

## Mevcut v2 vault'u taşımak

Bu bölüm yalnız daha önce çekirdek v2'ye yükseltilmiş harici/eski bir vault'u elle tamamlamak veya
onarım yapmak içindir. v1'den güncel Respected Brain'e geçiyorsan bunu ayrıca çalıştırma;
`scripts/upgrade.sh` çekirdek ve multi-AI katmanını tek doğrulanmış işlemde birlikte kurar.

Komut önce yalnızca nelerin yönetileceğini gösterir:

```bash
python3 scripts/enable_multiai.py "/mutlak/yol/Vault"
```

Çıktıyı kontrol ettikten sonra uygula:

```bash
python3 scripts/enable_multiai.py "/mutlak/yol/Vault" --apply
```

Windows uygulamaları + WSL kullanıyorsan ve otomatik algılama mümkün değilse profili açıkça ver:

```bash
python3 scripts/enable_multiai.py "/mnt/c/Users/<ad>/Documents/<vault-adı>" --platform windows-wsl --apply
```

Bu profil Cursor ve Antigravity'nin Windows hook komutlarını `wsl.exe --cd <vault>` üzerinden
çalıştırır; Windows uygulamasının başlangıç klasörüne güvenmez;
hafıza motoru WSL'deki Python/Bash ortamında kalır, Obsidian aynı klasörü `C:\...` yolundan açar.

İlk geçişte kişiselleştirilmiş `CLAUDE.md`, `.beyin/instructions.md` için kaynak alınır; böylece
isim, biyografi ve davranış ayarları kaybolmaz. Üzerine yazılacak üretilmiş adaptörler
`.beyin/backups/<tarih-saat>/` altında yedeklenir.

Codex proje hook'larını ilk kez gördüğünde `/hooks` ekranından güvenmeni ister. Cursor ve
Antigravity proje hook dosyalarını kendi standart konumlarından yükler.

## Her AI aracını bütün kod projelerinde vault'a bağlamak

Vault'un adı serbesttir: `respectedOS`, `Ada Brain`, `Notlarım` veya başka bir ad olabilir.
Araçların başka kod repolarında çalışırken de merkezi vault'u bulması için kullanıcı düzeyi
bağlantıyı kur:

```bash
python3 scripts/install_global.py \
  "/mnt/c/Users/<ad>/Documents/<vault-adı>" \
  --home "/mnt/c/Users/<ad>" \
  --antigravity-home "/home/<wsl-adı>" \
  --platform windows-wsl \
  --providers all
```

Önizlemeyi kontrol ettikten sonra `--apply` ekle. `all` yerine virgülle `antigravity,codex`,
`codex,cursor` gibi seçim yapılabilir. Kurucu mevcut kullanıcı kurallarını, hook'larını ve ayarlarını
korur; yönettiği Respected bloklarını birleştirir, yedek alır ve ortak skill'leri her aracın kullanıcı
düzeyi konumuna kopyalar. Global hook, vault kendi workspace'i olarak açıksa proje hook'unu
çift çalıştırmaz. Böylece aktif kod reposu başka yerde olsa da konuşma özeti seçilen vault'a yazılır.
`--antigravity-home` yalnız Antigravity IDE'yi **Connect to WSL** modunda da kullananlar içindir.
Linux profilindeki `.gemini` kökünü ayrıca kurar; seçenek tekrarlanabilir ve diğer provider'ları bu
ek köklere taşımaz. Yalnız Windows profilini kullananlar seçeneği atlayabilir.

Windows uygulamalarını WSL olmadan doğrudan kullanmak için aynı kurucuyu PowerShell'de native
profille çalıştır:

```powershell
py -3 scripts/install_global.py `
  "C:\Users\<ad>\Documents\<vault-adı>" `
  --home "C:\Users\<ad>" `
  --platform windows-native `
  --providers codex,cursor
```

Bu profil hook'larda `py.exe -3` ve vault içindeki `bridge.py` dosyasının mutlak Windows yolunu
kullanır; WSL, Bash veya `.sh` dosyası gerektirmez. `--providers` seçimi ana agent tercihi
değildir: yalnız kurulu araçların hangilerine global bağlantı yazılacağını belirler. Bugün Codex ve
Cursor ile başlayıp daha sonra `antigravity` veya `claude` ekleyebilirsin; mevcut kişisel kurallar
ve diğer provider ayarları korunur. Herkesin vault adı da kendine aittir, `respectedOS` zorunlu
değildir.

## Arka plan modeli nasıl seçilir?

Hook hangi araçtan geldiyse önce onun yerel CLI'ı denenir. Antigravity için `agy`, Codex için
`codex`, Claude için `claude`, Cursor için `cursor-agent` kullanılır. Tercih edilen CLI kurulu
değilse diğerleri denenir. Kota, rate-limit, geçici kapasite, timeout veya 5xx servis hatasında
otomatik olarak sıradaki kullanılabilir CLI'a geçilir; kimlik doğrulama ve kalıcı yapılandırma
hataları gizlenmez.

Varsayılan `auto` ayarını değiştirmek gerekmez. Kullanıcı özellikle başka bir özetleyiciyi ilk
tercih yapmak isterse vault içinde kalıcı seçim yapılabilir:

```bash
python3 scripts/set_summary_provider.py auto
python3 scripts/set_summary_provider.py codex   # claude | codex | antigravity | cursor
```

Bu ayar coding agentı sabitlemez; yalnız arka plan özeti ve bilgi derlemesinde denenecek ilk CLI'ı
seçer. Seçilen CLI geçici kota/servis hatası verirse fallback devam eder. Geçici shell oturumları
için `BEYIN_MODEL_PROVIDER` ortam değişkeni dosyadaki seçimin önüne geçebilir.

Başka bir yerel model komutu kullanmak istersen komut prompt'u stdin'den almalıdır:

```bash
export BEYIN_LLM_COMMAND="yerel-model-komutum --text"
```

Dosyalar yerelde kalır; özetlenecek konuşma seçilen CLI'ın modeline gider. Derleme yine izole
staging klasöründe yapılır ve yalnızca izin verilen `knowledge/` dosyaları vault'a taşınır.

### “Bilgi derleme” gerçekte ne zaman çalışır?

Sistem pencere veya alarm açmaz. Her oturum kapanışında konuşma `daily/YYYY-MM-DD.md` dosyasına
sessizce özetlenir. Bilgi derlemesi (`compile.py`) sabah 08:00 zamanlayıcısında sabah brifingi
öncesinde dünün ve önceki günlerin loglarını işler. Kaçırılan günler varsa sonraki agent
başlangıcı tamamlanmış önceki günleri catch-up olarak derler; içinde bulunulan günün hâlâ değişen
daily dosyasını erken derlemez.

## Tarihsel kaynaklardan yenilik incelemek

Respected Brain bağımsız geliştirilir; Avenox Beyin ve topluluk dalları otomatik olarak merge
edilmez. Dışarıdaki bir düzeltme önce davranış ve lisans açısından incelenir, ardından gerekliyse
tek kaynaklı ve provider-neutral mimariye yeniden uyarlanır. Son incelenen SHA'lar, alınan
düzeltmeler ve ertelenen fikirler `docs/UPSTREAM-SYNC.md` ile
`docs/UPSTREAM-ADOPTION-BACKLOG.md` dosyalarında tarihsel kanıt olarak tutulur.

## Bilinen sınırlar

- Antigravity'de tam bir SessionStart olayı olmadığı için ilk `PreInvocation` başlangıç olarak
  kullanılır; `Stop` kapanış özetini başlatır.
- Cursor `preCompact` olayı transkript yolu vermeyebilir. Böyle durumda flush güvenli biçimde
  atlanır; `sessionEnd` normal kapanış hattıdır.
- Codex proje hook'ları değiştiğinde güven kaydı hash'e bağlı olduğundan yeniden inceleme ister.
- Antigravity masaüstü uygulaması ile Antigravity CLI ayrı parçalardır. Arka plan özetlerinin
  Antigravity kotasını kullanması için `agy` CLI kurulu ve oturum açmış olmalıdır; yalnız IDE
  kuruluysa sistem kullanılabilir başka CLI'a geçer.
- Cursor kotasını kullanmak için `cursor-agent` CLI kurulu ve oturum açmış olmalıdır.
- Multi-AI `1.4.0`, ortak Python lifecycle, görünür otomatik haritalar, provider-neutral sabah
  brifingi, portable lock/process katmanı, üç deterministik profil, transactional updater,
  native Windows installer, model çıktısı normalizasyonu, 1-shot şema onarımı,
  provider-neutral immutable handoff event log mimarisi, Linux CI kapısı ve opt-in Restic/Git yedekleme araçlarını kapsar.
