# Respot Brain — çoklu AI kullanımı

Bu dalda vault tek bir AI aracına ait değildir. Claude Code, Codex, Cursor ve Antigravity aynı
Markdown hafızasını, kuralları, skill'leri ve günlük/knowledge hattını paylaşır.

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
onarım yapmak içindir. v1'den güncel Respot Brain'e geçiyorsan bunu ayrıca çalıştırma;
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
  --platform windows-wsl \
  --providers all
```

Önizlemeyi kontrol ettikten sonra `--apply` ekle. `all` yerine virgülle `antigravity,codex`,
`codex,cursor` gibi seçim yapılabilir. Kurucu mevcut kullanıcı kurallarını, hook'larını ve ayarlarını
korur; yönettiği Respot bloklarını birleştirir, yedek alır ve ortak skill'leri her aracın kullanıcı
düzeyi konumuna kopyalar. Global hook, vault kendi workspace'i olarak açıksa proje hook'unu
çift çalıştırmaz. Böylece aktif kod reposu başka yerde olsa da konuşma özeti seçilen vault'a yazılır.

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

### “Gece derleme” gerçekte ne demek?

Sistem saat 18:00 için alarm veya görev kurmaz ve ChatGPT/Antigravity penceresi açmaz. Her oturum
kapanışında önce konuşma `daily/YYYY-MM-DD.md` dosyasına özetlenir. Bu kapanış yerel saate göre
18:00'den sonraysa ve derlenmemiş günlük varsa aynı arka plan süreci headless CLI ile
`knowledge/` derlemesini başlatır. O akşam 18:00'den sonra hiç oturum kapatmazsan sonraki agent
başlangıcı tamamlanmış önceki günleri catch-up olarak derler; içinde bulunulan günün hâlâ değişen
daily dosyasını erken derlemez.

## Upstream yeniliklerini almak

Bu fork'ta orijinal depo `upstream` adıyla tutulur. Önce yalnızca kontrol et:

```bash
./scripts/upstream_sync.sh check
```

Yeni commit'leri kontrollü birleştirmek için çalışma ağacını temizle ve:

```bash
./scripts/upstream_sync.sh merge
```

Script bir geri dönüş dalı oluşturur ve birleştirmeyi commit etmeden çalışma ağacına bırakır.
Testleri çalıştırıp farkı incelemeden commit atma. Tek bir upstream düzeltmesi gerekiyorsa
`git cherry-pick <commit>` daha az çakışma üretir.

Respot için tercih edilen yöntem tam merge değil, davranışı provider-neutral katmana uyarlamaktır.
Son incelenen SHA'lar, alınan düzeltmeler ve ertelenen dallar `docs/UPSTREAM-SYNC.md` dosyasında
kayıtlıdır.

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
