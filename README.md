# 🧠 Respot Brain: araç bağımsız, hatırlamayı unutmayan ikinci beyin

[Obsidian](https://obsidian.md) ile Claude Code, Codex, Cursor ve Antigravity üstünde çalışan,
açık kaynak bir **ikinci beyin**. Yerel bir Markdown vault, kalıcı hafıza, sıfır bağımlılık,
sıfır ekstra ücret. Dosya yönetmezsin, konuşursun.

Bu dalın temel farkı araç bağımsızlığıdır: ortak talimatlar `.beyin/instructions.md` içinde,
skill'ler `.beyin/skills/` altında tek kez tutulur; `CLAUDE.md`, `AGENTS.md`, Cursor rules ve
Antigravity rules/hook dosyaları buradan üretilir. Ayrıntılar ve mevcut v2 vault'u güvenli taşıma
komutu için [MULTI_AI.md](MULTI_AI.md) dosyasına bak.

Vault adı kullanıcıya aittir; `respectedOS` veya başka sabit bir ad zorunlu değildir. İsteğe bağlı
global kurulum, seçilen vault'u Claude, Codex, Cursor ve Antigravity'ye kullanıcı düzeyinde
bağlayarak başka kod repolarında da aynı merkezi hafızayı kullanır.

## Kısaca nasıl çalışır?

Respot bir sohbet uygulaması veya yeni bir model değildir. Agentların arasında duran ortak,
dosya tabanlı hafıza katmanıdır:

```text
Antigravity ─┐
Codex ───────┼─→ aynı vault → daily/ → knowledge/ → sonraki agent oturumu
Claude ──────┤
Cursor ──────┘
```

Bir projeye Antigravity ile başlayıp ertesi gün Codex'e geçebilirsin. Codex, Antigravity'nin özel
sohbet ekranını veya bütün ham geçmişini devralmaz; bunun yerine ortak vault'taki son oturum,
aktif konular, kararlar, kurallar, günlük özetleri ve bilgi indeksini alır. Araç değiştirirken
taşınabilir olan şey **iş bağlamıdır**, sağlayıcının kendi sohbet arayüzü değildir.

**v1'in tezi devamlılıktı: oturum açılınca geçen oturum bağlama giriyordu.** İşe yarıyordu ama tek
bir kırılgan varsayıma dayanıyordu: modelin oturum biterken hafıza dosyalarını güncellemeyi
hatırlaması. Hatırlamadığı her seferde o gün kayboluyordu. **v2'nin tezi şu: hafıza rica değil,
mekanizmadır.** Artık oturum kapanışını bir kanca yakalıyor, konuşmayı arka planda özetleyip
`daily/` altına günlük log olarak yazıyor, akşamları günde bir kez bir derleyici o logları
`knowledge/` altında birbirine bağlanan makalelere dönüştürüyor. Ertesi sabah bu bilgi tabanının
indeksi kendiliğinden bağlama giriyor. Kimsenin bir şey yazmayı hatırlaması gerekmiyor.

Video izlemene gerek yok. Kurulum ve günlük kullanım bu README'de; ayrıntılı davranış ve bakım
notları [MULTI_AI.md](MULTI_AI.md), coding agentın uygulayacağı kurulum runbook'u [SETUP.md](SETUP.md)
içindedir.

---

## Hızlı başlangıç

Native Windows'ta WSL kullanmadan sıfırdan kurulum yapacaksan doğrudan
[SETUP-WINDOWS.md](SETUP-WINDOWS.md) içindeki PowerShell akışını kullan. macOS, Linux ve
Windows+WSL için aşağıdaki agent destekli `SETUP.md` akışı geçerlidir.

### 1. Forku klonla

```bash
git clone https://github.com/respected0/respot-brain.git
cd respot-brain
```

### 2. Bu klasörü tercih ettiğin coding agentta aç

Antigravity, Codex, Claude Code veya Cursor'a şunu yaz:

```text
SETUP.md dosyasını tamamen oku ve ikinci beynimi kurmak için adımları uygula.
Vault adını ve yolunu bana sor. Kullandığım agentları global bağla. Özetleyici tercihini auto bırak.
```

Agent; adını, kullanım amacını, AI ortağının adını, vault adını/yolunu ve hangi araçları
kullandığını sorar. Önizlemeyi gösterir, onayından sonra kurar ve test eder.

### 3. Kurulumdan sonra normal projeni aç

Global bağlantıyı seçtiysen vault klasöründe çalışmak zorunda değilsin. Herhangi bir kod reposunu
desteklenen agentlardan biriyle aç; ilk oturumda ortak hafıza bağlama girer, kapanışta özet merkezi
vault'a yazılır. Codex yeni global hook'u ilk kez gördüğünde `/hooks` ekranından bir defalık güven
isteyebilir.

### Agent kullanmadan elle global kurulum

Kurulum agentı olmadan da aynı işlemi yapabilirsin. Komut ilk çalıştırmada yalnız önizleme
gösterir; dosya yazmak için sonucu kontrol edip `--apply` ekle.

Windows + WSL örneği:

```bash
python3 scripts/install_global.py "/mnt/c/Users/KULLANICI/Documents/BenimBeynim" \
  --home "/mnt/c/Users/KULLANICI" --platform windows-wsl --providers all

# Önizleme doğruysa:
python3 scripts/install_global.py "/mnt/c/Users/KULLANICI/Documents/BenimBeynim" \
  --home "/mnt/c/Users/KULLANICI" --platform windows-wsl --providers all --apply
```

Native Windows PowerShell örneği:

```powershell
py -3 scripts/install_global.py `
  "C:\Users\KULLANICI\Documents\BenimBeynim" `
  --home "C:\Users\KULLANICI" `
  --platform windows-native `
  --providers codex,cursor
```

macOS/Linux örneği:

```bash
python3 scripts/install_global.py "/mutlak/yol/BenimBeynim" \
  --home "$HOME" --platform portable --providers all
```

`--providers all` yerine yalnız kullandığın araçları virgülle yazabilirsin. Kurucu mevcut global
kurallarını silmez; yönetilen Respot bölümünü birleştirir ve değişecek dosyaları yedekler. Vault'un
adı serbesttir.

## Agent değiştirmek

Ekstra taşıma komutu yoktur:

1. İlk agentın oturumunu normal biçimde bitir ve günlük özetin yazılması için birkaç saniye ver.
2. Aynı veya başka projeyi diğer agentta aç.
3. Yeni agent global/project hook üzerinden aynı vault bağlamını alır.

Örnek: Antigravity'de alınan karar kapanışta `daily/` dosyasına yazılır; Codex açıldığında son
oturum ve bilgi indeksi bağlama eklenir. Henüz kapanmamış veya özetlenmemiş son birkaç mesajın
aktarılması garanti değildir; kritik bir geçişte ilk agent oturumunu kapatmak önemlidir.

## Özetlemeyi hangi AI yapar, limit biterse ne olur?

Varsayılan `auto` modudur ve çoğu kullanıcı bunu değiştirmemelidir:

1. Oturum hangi agenttan geldiyse önce onun CLI'ı denenir.
2. CLI kurulu değilse sıradaki kurulu sağlayıcı denenir.
3. Kota/rate-limit, timeout, geçici kapasite veya 5xx hatasında otomatik fallback yapılır.
4. Kimlik doğrulama veya bozuk yapılandırma gibi kalıcı hata gizlenmez; düzeltilmesi için raporlanır.

Örnek: Codex oturumunun kapanışında Codex limiti bittiyse ve Claude veya `agy` kurulu ve giriş
yapılmışsa özet onlardan biriyle tamamlanabilir. Fallback yalnız makinede kurulu ve oturum açılmış
CLI'lar arasında çalışır.

İsteyen kullanıcı özetleyicinin ilk tercihini vault içinde kalıcı olarak değiştirebilir:

```bash
python3 scripts/set_summary_provider.py auto          # önerilen
python3 scripts/set_summary_provider.py claude
python3 scripts/set_summary_provider.py codex
python3 scripts/set_summary_provider.py antigravity
python3 scripts/set_summary_provider.py cursor
```

Bu seçim kod yazdığın ana agentı değiştirmez; yalnız kapanış özeti ve bilgi derlemesinde önce hangi
yerel CLI'ın çağrılacağını belirler. Seçilen sağlayıcı geçici olarak kullanılamazsa fallback devam eder.

### Zaten v1 beynin varsa

Aynı komut yeter. `SETUP.md` önce mevcut bir beyin arar, bulursa yükseltme moduna geçer ve işi
tek bir script'e devreder: `scripts/upgrade.sh`. Bu işlem ara bir “avenoxbeyin v2” kurulumu
bırakmaz; çekirdek v2 dosyalarını, tek-kaynak agent talimatlarını ve Claude/Codex/Cursor/
Antigravity adapterlarını aynı doğrulanmış işlem içinde kurarak doğrudan **Respot Brain**'e
yükseltir. Yükseltme **sadece ekler**: mevcut hafıza dosyalarına, Dashboard'a ve notlarına
dokunulmaz. Yalnız eski çekirdek `2.0.0` damgası bulunan yarım bir kurulum da eksik Respot
katmanı tamamlanmadan “güncel” sayılmaz.

Damgasız v1 vault'un native Windows dönüşümü henüz desteklenmez; bu özel durumda doğrulanmış WSL
`upgrade.sh` yolu kullanılmalıdır. Native Windows, sıfırdan kurulum ve damgalı Respot
`1.0.0 → 1.1.0` güncellemesi için desteklenir.

Üç şeyi peşinen bilmen iyi olur:

- **Hafıza klasörünün adı `🔮 850-Companion` olmak zorunda.** Kancalar ve scriptler bu sabit yolu
  okuyor. Klasörün adı ortağının adıysa (`🔮 850-Echo` gibi) script bunu `git mv` ile değiştirmeyi
  teklif eder. İçerik hiç değişmez, sadece klasör adı değişir. Hayır dersen yükseltme hiç
  başlamaz ve vault'a Respot damgaları vurulmaz; yarım kurulmuş bir sistemden dürüst bir v1 iyidir.
- **İlk iş git anlık görüntüsü.** Alınamazsa yükseltme durur, devam etmez. Geri dönüş her zaman
  açık.
- **İki sürüm damgası en sona yazılır.** Kancalar, scriptler, adapter drift'i, placeholder'lar,
  kanca sayısı ve `.gitignore` koruması tek tek doğrulandıktan sonra önce multi-AI, ardından
  yetkili çekirdek damgası yazılır. Bir kapı bile geçilmezse ikisi de yazılmaz.

---

## v1 → Respot Brain

| | v1 | Respot Brain |
| --- | --- | --- |
| Günlük hafıza | model hatırlarsa yazar | oturum kapanışında **otomatik** yazılır |
| Kanca sayısı | 3 | 4 (`PreCompact` eklendi) |
| Compaction | konuşma sıkıştırılınca kaybolur | sıkıştırma öncesi yakalanır |
| Bilgi tabanı | yok | `knowledge/` altında derlenmiş, birbirine bağlı makaleler |
| Oturum başı bağlam | son oturum + threadler | + kurallar, son journal, bilgi indeksi, bugünün logu |
| Kalıcı kurallar | yok | `Kurallar.md`, "bunu böyle yapma" dediğinde oraya yazılır |
| Sağlık kontrolü | yok | `beyin doktor` skill'i, tek tabloda tanı |
| Eski geçmiş | yok | `geçmiş import`: ChatGPT, Claude, Gemini dışa aktarımları |
| Yükseltme | yok | yerinde, ekleme yapan, tekrar çalıştırılabilir |
| Bağımlılık | bash | Python 3; POSIX'te ince Bash uyumluluk launcherları, native Windows'ta Bash yok |

---

## Mimari

```
   oturum biter                    konuşma sıkışmak üzere
   (SessionEnd)                         (PreCompact)
        |                                    |
        v                                    v
  session-end.sh                       pre-compact.sh
        |                                    |
        +------------------+-----------------+
                           v
                       flush.py   (claude / codex / agy / cursor-agent / özel CLI)
                  transkripti okur, Türkçe özet çıkarır
                           v
                 daily/YYYY-MM-DD.md      <-- makine yazar, sen değil
                           |
        (saat 18'den sonra, günde bir kez, değişen log varsa)
                           v
                      compile.py          (seçilen yerel AI CLI)
                           v
   knowledge/concepts/*.md + knowledge/connections/*.md + knowledge/index.md
                           |
                           v
                   session-start.sh
        indeksi + bugünün logunu + hafızayı bir sonraki oturuma enjekte eder
```

Yazma tarafı makineye ait, ilişki katmanı sana ait: ortağın hâlâ `Last-Session.md` ve `Threads.md`
dosyalarını kendi eliyle günceller. Makine katmanı onun yerine geçmez, altını doldurur.

### Agent uyumluluk tablosu

| Agent | Ortak talimat | Skill kaynağı | Oturum kancaları | Arka plan özetleyici |
| --- | --- | --- | --- | --- |
| Antigravity | `.agents/rules/beyin.md` | `.agents/skills/` | başlangıç + kapanış | `agy` |
| Codex | `AGENTS.md` | `.agents/skills/` | başlangıç, prompt, kapanış, pre-compact | `codex exec` |
| Cursor | `.cursor/rules/beyin.mdc` + `AGENTS.md` | `.agents/skills/` | başlangıç, prompt, kapanış, pre-compact | `cursor-agent -p` |
| Claude Code | `CLAUDE.md` | `.claude/skills/` | başlangıç, prompt, kapanış, pre-compact | `claude -p` |

Talimat ve skill içerikleri `.beyin/` altındaki tek kaynaktan üretilir; yani dört ayrı kopyayı
elle güncellemezsin. Dosya adları ve kanca olayları agentların kendi formatları farklı olduğu için
aynı değildir, fakat verdikleri hafıza davranışı ortaktır.

## Ne alıyorsun

```
{Ad}OS/
├── 📥 000-Inbox/Dump/        # ham yakalama
├── 🎯 100-Command-Center/    # Dashboard
├── 🏰 300-Projects/          # proje başına bir klasör
├── 🧠 500-Knowledge/         # insanın yazdığı notlar
├── 🛠️ 600-Arsenal/           # araçlar, kişiler, kaynaklar
├── 🔮 850-Companion/         # ortağın kalıcı hafızası (+ Kurallar.md)
├── daily/                    # makine yazar: günlük loglar
├── knowledge/                # makine derler: makaleler + bağlantılar + indeks
├── 📦 900-Archive/
├── 📋 Templates/
├── .beyin/                   # tek kaynak: talimatlar, skill'ler, ortak adaptör
├── .claude/                  # ortak çekirdek runtime + Claude adapteri (v2 uyumluluk yolu)
├── .codex/                   # Codex hook'ları
├── .cursor/                  # Cursor rules ve hook'ları
└── .agents/                  # Antigravity rules, skill ve hook'ları
```

- **İsmini sen koyduğun bir AI ortağı.** Varsayılan dili Türkçe.
- **Süreklilik motoru.** Dört sıfır bağımlılıklı kanca, her açılışta hafızayı bağlama koyar, her
  kapanışta oturumu diske yazar.
- **Dosya tabanlı hafıza.** API anahtarı yok, ücretli servis yok, her şey senin diskinde.
- **Opsiyonel semantik hafıza.** [mem0](https://mem0.ai) ücretsiz katmanı üstüne anlamsal arama
  ekler, temel sürümü tamamen ücretsiz ve kredi kartı istemez. İstemezsen sistem eksiksiz çalışır.
- **Tek tık başlatıcı.** macOS'ta masaüstünde 🧠 ikonlu bir uygulama vault'u anında açar. Linux'ta
  yerine bir `.desktop` kısayolu yazılır (test edilmedi).

## Maliyet, dürüst hâliyle

Ekstra bir API anahtarı gerekmez; arka plan özetleyici ve derleyici seçilen yerel CLI'ın mevcut
oturumunu/aboneliğini kullanır. Hangi sağlayıcı özeti çıkarırsa kullanım onun kotasına yazılır.
Birden fazla CLI kuruluysa geçici limitlerde otomatik fallback yapılabilir.

## Gereksinimler

Zorunlu, her platformda: desteklenen yerel AI CLI'lardan en az biri (`claude`, `codex`, `agy`,
`cursor-agent`), [Obsidian](https://obsidian.md) ve Python 3. POSIX/WSL komutu `python3`, native
Windows komutu `py.exe -3` olur. Python opsiyonel değil: günlük log da bilgi derlemesi de onun
üstünde çalışır.

| Platform | Durum | Ne çalışır, ne çalışmaz |
| --- | --- | --- |
| macOS | **orijinal akış test edildi** | ortak runtime, `daily/`, `knowledge/`, 🧠 masaüstü kısayolu; multi-AI adaptörleri otomatik testlidir. |
| Linux | **test edilmedi** | kurulum `uname` ile dallanır: Homebrew, Obsidian cask ve macOS `.app` adımları atlanır, yerine XDG `.desktop` kısayolu yazılır. Vault, kancalar ve scriptler taşınabilir yazıldı ama gerçek bir Linux masaüstünde doğrulanmadı. Denersen sorun aç. |
| Windows + WSL | **doğrulandı** | Windows Antigravity/Cursor hook'ları `wsl.exe` ile WSL'deki Python motoruna bağlanır; Obsidian aynı vault'u Windows yolundan açar. |
| Windows native | **Windows CI doğrulandı; gerçek iki-provider smoke bekliyor** | `py.exe -3` ile ortak Python lifecycle doğrudan çalışır; WSL/Bash gerekmez. Taze kurulum ve damgalı Respot güncellemesi desteklenir, damgasız v1 dönüşümü henüz WSL ister. |

Masaüstü kısayolu macOS'ta `osacompile` ve AppKit kullanır, ikisi de Linux'ta yoktur. Vault'un
kendisi düz Markdown, yani her yerde açılır. Windows + WSL global multi-agent köprüsü doğrulandı;
Linux masaüstü kısayolu hâlâ saha testi bekliyor.

## Sık sorulan sorular

### Vault'un adı `respectedOS` olmak zorunda mı?

Hayır. Bu yalnız bir kullanıcının kişisel seçimidir. Kurulumda verilen herhangi bir klasör adı ve
mutlak yol kullanılabilir. İçerideki `🔮 850-Companion` klasörü ise runtime sözleşmesinin sabit
parçasıdır; AI ortağının görünen adı dosyaların içindedir.

### Her agentın hesabına ayrıca giriş gerekir mi?

Yalnız kullanmak istediğin sağlayıcıların yerel CLI'larına giriş gerekir. En az bir desteklenen CLI
yeterlidir; otomatik fallback için birden fazlasının kurulu ve giriş yapılmış olması gerekir.

### Aynı anda iki agent kullanabilir miyim?

Evet. Günlük yazımı kilit ve tekrar kontrolüyle korunur. Yine de aynı dosyayı iki agentın aynı anda
düzenlemesi normal git/uygulama çakışması yaratabilir; bu hafıza sisteminden bağımsızdır.

### Saat 18.00'de bilgisayar kendi kendine agent açar mı?

Hayır. Zamanlanmış görev yoktur. 18.00'den sonraki ilk uygun oturum kapanışı derlemeyi tetikler.
Bu pencere kaçırılırsa sonraki agent başlangıcı yalnız tamamlanmış önceki günleri catch-up olarak
derler; bugünün henüz tamamlanmamış loguna dokunmaz.

## Bir şey ters giderse

Vault klasöründe kullandığın ajana `beyin doktor` yaz. Kancalar, scriptler, python3, yerel AI CLI,
günlük log tazeliği, son derleme durumu, iCloud çakışma dosyaları ve git durumu tek tabloda gelir,
her kırmızı satırın altında düzeltme komutu yazar.

---

## Credits

Bilgi derleme mimarisi Andrej Karpathy'nin LLM bilgi tabanı desenine dayanır:
https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f

Geri kalanı [Avenox](https://avenox.lol) günlük kullandığı sistemden, kişisel veriden arındırılıp
herkes için genelleştirilerek çıkarıldı.

## Lisans

MIT, [LICENSE](LICENSE) dosyasına bak. PR'lar açık.

---

## In English (short version)

**Respot Brain** is a multi-AI fork of avenoxbeyin: an open-source Obsidian second brain for Claude Code, Codex, Cursor,
and Antigravity. It keeps one canonical instruction and skill source, then generates each agent's
native rules and hooks. Session-end and pre-compaction events feed conversations into `daily/`;
the selected local CLI (`claude`, `codex`, `agy`, or `cursor-agent`) compiles those logs into linked articles under
`knowledge/`. The next session starts with that knowledge index already in context.

Install: `git clone https://github.com/respected0/respot-brain.git && cd respot-brain`, then ask
your coding agent to read and follow `SETUP.md`. Already running v1?
The same command detects it and hands the work to one committed script, `scripts/upgrade.sh`.
That transaction upgrades directly to Respot Brain: core v2 plus the shared instruction source and
Claude/Codex/Cursor/Antigravity adapters. It does not leave an intermediate avenoxbeyin-v2 install.
It is additive only, your memory files are never touched, the settings merge is idempotent, and it takes
a **verified** git snapshot before it changes anything. A core-only `2.0.0` vault is completed rather
than treated as current. Two things it will ask you about, and stop
for if you say no: renaming the memory folder to the fixed `🔮 850-Companion` path (a `git mv`, the
contents never move), and removing v1 hook wiring left behind in `settings.local.json` so hooks
stop firing twice. Neither version stamp is written early: after every gate passes, the multi-AI
stamp is written first and the authoritative `.beyin-version` stamp is the final write.

Platform honesty: the original macOS path remains supported. Linux desktop remains unverified.
Windows + WSL remains verified with Windows-side hooks invoking the Python memory engine through
`wsl.exe`. Native Windows fresh install and stamped Respot updates use `py.exe -3` without WSL or
Bash; unstamped v1 migration still uses WSL. A provider-neutral global installer can connect any
named vault to Claude, Codex, Cursor and Antigravity across unrelated code repositories.

Users may switch coding agents without migrating the vault. `auto` prefers the agent that emitted
the hook; a persistent first-choice summarizer can be selected with `set_summary_provider.py`, and
retryable quota/timeout/5xx failures fall back to another installed authenticated CLI.

No extra API key is required: background work uses an authenticated local AI CLI. The core uses
the Python standard library; POSIX keeps thin Bash compatibility launchers. Knowledge-compilation
architecture credit:
Andrej Karpathy's LLM knowledge base pattern,
https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f. MIT licensed.
