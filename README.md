# 🧠 avenoxbeyin multi-AI: hatırlamayı unutmayan ikinci beyin

[Obsidian](https://obsidian.md) ile Claude Code, Codex, Cursor ve Antigravity üstünde çalışan,
açık kaynak bir **ikinci beyin**. Yerel bir Markdown vault, kalıcı hafıza, sıfır bağımlılık,
sıfır ekstra ücret. Dosya yönetmezsin, konuşursun.

Bu dalın temel farkı araç bağımsızlığıdır: ortak talimatlar `.beyin/instructions.md` içinde,
skill'ler `.beyin/skills/` altında tek kez tutulur; `CLAUDE.md`, `AGENTS.md`, Cursor rules ve
Antigravity rules/hook dosyaları buradan üretilir. Ayrıntılar ve mevcut v2 vault'u güvenli taşıma
komutu için [MULTI_AI.md](MULTI_AI.md) dosyasına bak.

**v1'in tezi devamlılıktı: oturum açılınca geçen oturum bağlama giriyordu.** İşe yarıyordu ama tek
bir kırılgan varsayıma dayanıyordu: modelin oturum biterken hafıza dosyalarını güncellemeyi
hatırlaması. Hatırlamadığı her seferde o gün kayboluyordu. **v2'nin tezi şu: hafıza rica değil,
mekanizmadır.** Artık oturum kapanışını bir kanca yakalıyor, konuşmayı arka planda özetleyip
`daily/` altına günlük log olarak yazıyor, akşamları günde bir kez bir derleyici o logları
`knowledge/` altında birbirine bağlanan makalelere dönüştürüyor. Ertesi sabah bu bilgi tabanının
indeksi kendiliğinden bağlama giriyor. Kimsenin bir şey yazmayı hatırlaması gerekmiyor.

Video izlemene gerek yok, kurulum videosu da yok. Orijinal Claude kurulumu aşağıdaki gibi çalışır;
çoklu-AI katmanı ve mevcut vault taşıma adımları için [MULTI_AI.md](MULTI_AI.md) dosyasına bak.

---

## Hızlı başlangıç

Terminalde `claude` çalıştır ve şunu yapıştır:

```
Read https://avenox.lol/beyin.md and follow it exactly to build my second brain.
```

Ya da multi-AI fork'unu doğrudan klonla:

```bash
git clone https://github.com/respected0/respot-brain.git
cd respot-brain
```

Kullandığın coding agent'a `Read SETUP.md and follow it exactly to set up my second brain from
this template.` yaz. Agent birkaç soru sorar (adın, ne iş yaptığın, AI ortağının adı), vault'u
kurar ve uygun araç adaptörlerini bağlar.

### Zaten v1 beynin varsa

Aynı komut yeter. `SETUP.md` önce mevcut bir beyin arar, bulursa yükseltme moduna geçer ve işi
tek bir script'e devreder: `scripts/upgrade.sh`. Yükseltme **sadece ekler**: mevcut hafıza
dosyalarına, Dashboard'a, notlarına dokunulmaz. `daily/`, `knowledge/`, scriptler ve skill'ler
eklenir, dört kanca dosyası yenisiyle değiştirilir, `settings.json` kanca kaydı tekrar tekrar
çalıştırılabilecek şekilde birleştirilir.

Üç şeyi peşinen bilmen iyi olur:

- **Hafıza klasörünün adı `🔮 850-Companion` olmak zorunda.** Kancalar ve scriptler bu sabit yolu
  okuyor. Klasörün adı ortağının adıysa (`🔮 850-Echo` gibi) script bunu `git mv` ile değiştirmeyi
  teklif eder. İçerik hiç değişmez, sadece klasör adı değişir. Hayır dersen yükseltme hiç
  başlamaz ve vault'a v2 damgası vurulmaz; yarım kurulmuş bir v2'den dürüst bir v1 iyidir.
- **İlk iş git anlık görüntüsü.** Alınamazsa yükseltme durur, devam etmez. Geri dönüş her zaman
  açık.
- **Sürüm damgası en sona yazılır.** Kancalar, scriptler, placeholder'lar, kanca sayısı ve
  `.gitignore` koruması tek tek doğrulandıktan sonra. Bir kapı bile geçilmezse `.beyin-version`
  yazılmaz.

---

## v1 → v2

| | v1 | v2 |
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
| Bağımlılık | bash | bash + python3 (ikisi de sistemde var) |

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
                       flush.py           (claude / codex / agy / özel CLI)
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
├── .claude/                  # Claude uyumluluk ve süreklilik motoru
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
oturumunu/aboneliğini kullanır. Claude seçilirse eski Haiku/Sonnet davranışı korunur; Codex veya
Antigravity seçilirse onların yerel headless komutu kullanılır.

## Gereksinimler

Zorunlu, her platformda: desteklenen yerel AI CLI'lardan en az biri (`claude`, `codex`, `agy`),
[Obsidian](https://obsidian.md) ve `python3` (macOS'ta Command Line Tools ile gelir). `python3`
opsiyonel değil: günlük log da gece derlemesi de onun üstünde çalışır.

| Platform | Durum | Ne çalışır, ne çalışmaz |
| --- | --- | --- |
| macOS | **test edildi** | hepsi: kancalar, `daily/`, `knowledge/`, 🧠 masaüstü kısayolu |
| Linux | **test edilmedi** | kurulum `uname` ile dallanır: Homebrew, Obsidian cask ve macOS `.app` adımları atlanır, yerine XDG `.desktop` kısayolu yazılır. Vault, kancalar ve scriptler taşınabilir yazıldı ama gerçek bir Linux masaüstünde doğrulanmadı. Denersen sorun aç. |
| Windows + WSL | **doğrulandı** | Windows Antigravity/Cursor hook'ları `wsl.exe` ile WSL'deki Python motoruna bağlanır; Obsidian aynı vault'u Windows yolundan açar. |

Masaüstü kısayolu macOS'ta `osacompile` ve AppKit kullanır, ikisi de Linux'ta yoktur. Vault'un
kendisi düz Markdown, yani her yerde açılır; kurulum akışının tamamı için doğrulanmış tek platform
şu an macOS.

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

**avenoxbeyin multi-AI** is an open-source Obsidian second brain for Claude Code, Codex, Cursor,
and Antigravity. It keeps one canonical instruction and skill source, then generates each agent's
native rules and hooks. Session-end and pre-compaction events feed conversations into `daily/`;
the selected local CLI (`claude`, `codex`, or `agy`) compiles those logs into linked articles under
`knowledge/`. The next session starts with that knowledge index already in context.

Install: `git clone https://github.com/respected0/respot-brain.git && cd respot-brain`, then ask
your coding agent to read and follow `SETUP.md`. Already running v1?
The same command detects it and hands the work to one committed script, `scripts/upgrade.sh`:
additive only, your memory files are never touched, the settings merge is idempotent, and it takes
a **verified** git snapshot before it changes anything. Two things it will ask you about, and stop
for if you say no: renaming the memory folder to the fixed `🔮 850-Companion` path (a `git mv`, the
contents never move), and removing v1 hook wiring left behind in `settings.local.json` so hooks
stop firing twice. The `.beyin-version` stamp is the last write of all, only after every gate
passes.

Platform honesty: the original macOS path remains supported. Linux desktop remains unverified.
Windows + WSL has been verified with Windows-side hooks invoking the Python memory engine through
`wsl.exe`; a global Antigravity installer can connect code repositories outside the vault.

No extra API key is required: background work uses an authenticated local AI CLI. The core uses
bash and the Python standard library. Knowledge-compilation architecture credit:
Andrej Karpathy's LLM knowledge base pattern,
https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f. MIT licensed.
