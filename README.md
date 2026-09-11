# 🧠 Respected Brain: araç bağımsız, hatırlamayı unutmayan ikinci beyin

<p align="center">
  <a href="https://github.com/respected0/respectedbrain/releases"><img src="https://img.shields.io/badge/Release-v0.0.1-blue.svg?style=flat-square" alt="Release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg?style=flat-square" alt="License"></a>
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB.svg?style=flat-square&logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux%20%7C%20WSL-lightgrey.svg?style=flat-square" alt="Platforms">
  <img src="https://img.shields.io/badge/Tested%20Agents-Antigravity%20%7C%20Codex%20%7C%20Claude%20%7C%20Cursor%20%7C%20Windsurf-purple.svg?style=flat-square" alt="Tested Agents">
  <img src="https://img.shields.io/badge/MCP-Supported%20FTS5-teal.svg?style=flat-square" alt="MCP Server">
  <img src="https://img.shields.io/badge/Architecture-Zero--Trust%20Local%20Memory-orange.svg?style=flat-square" alt="Local Memory">
</p>

[Obsidian](https://obsidian.md) ile Claude Code, Codex, Cursor ve Antigravity üstünde çalışan,
açık kaynak bir **ikinci beyin**. Yerel bir Markdown vault, kalıcı hafıza, sıfır bağımlılık,
sıfır ekstra ücret. Dosya yönetmezsin, konuşursun.

Respected Brain'in temel farkı araç bağımsızlığıdır: ortak talimatlar `.beyin/instructions.md` içinde,
skill'ler `.beyin/skills/` altında tek kez tutulur; `CLAUDE.md`, `AGENTS.md`, Cursor rules ve
Antigravity rules/hook dosyaları buradan üretilir. Ayrıntılar için [MULTI_AI.md](MULTI_AI.md)
dosyasına bak.

Vault'un adı kullanıcıya aittir; `respectedOS` veya başka sabit bir ad zorunlu değildir. İsteğe bağlı
global kurulum, seçilen vault'u Claude, Codex, Cursor ve Antigravity'ye kullanıcı düzeyinde
bağlayarak başka kod repolarında da aynı merkezi hafızayı kullanır.

## Kısaca nasıl çalışır?

Respected bir sohbet uygulaması veya yeni bir model değildir. Agentların arasında duran ortak,
dosya tabanlı hafıza katmanıdır:

```mermaid
graph TD
    subgraph Agents ["🤖 Desteklenen AI Ajanları & Editörler"]
        AGY["Antigravity IDE"]
        CDX["OpenAI Codex"]
        CLD["Claude Code"]
        CUR["Cursor IDE"]
        WND["Windsurf / Cline"]
    end

    subgraph Hooks ["⚡ Yaşam Döngüsü Kancaları (Lifecycle Hooks)"]
        H_START["session-start<br/>(Hafıza & Bilgi İndeksi Enjeksiyonu)"]
        H_PROMPT["user-prompt<br/>(Dinamik Hatırlama & Guardrails)"]
        H_COMPACT["pre-compact<br/>(Sıkışma Öncesi Yakalama)"]
        H_END["session-end<br/>(Oturum Kapanış Tetikleyici)"]
    end

    subgraph MemoryEngine ["🧠 Respected Brain Yerel Motoru"]
        FLUSH["flush.py<br/>(Yerel CLI ile Transkript Özetleyici)"]
        DAILY["daily/YYYY-MM-DD.md<br/>(Günlük Oturum Logları)"]
        COMPILE["compile.py<br/>(Karpathy LLM Bilgi Derleyicisi)"]
        KNOWLEDGE["knowledge/<br/>(Kavramlar, İlişkiler & İndeks)"]
        COMPANION["🔮 850-Companion/<br/>(Last-Session, Threads, Kurallar)"]
    end

    subgraph Access ["🔍 Dış Erişim & Entegrasyon"]
        MCP["Model Context Protocol (MCP)<br/>scripts/vault_mcp_server.py (SQLite FTS5)"]
        OBS["Obsidian Kasa Arayüzü<br/>(Yerel Markdown Görselleştirme)"]
    end

    AGY & CDX & CLD & CUR & WND -->|Oturum Başlar| H_START
    AGY & CDX & CLD & CUR & WND -->|Kullanıcı Mesajı| H_PROMPT
    CDX & CLD & CUR -->|Bağlam Taşmak Üzere| H_COMPACT
    AGY & CDX & CLD & CUR & WND -->|Oturum Biter| H_END

    H_COMPACT & H_END --> FLUSH
    FLUSH --> DAILY
    DAILY -->|Saat 18+ / Sabah Brifingi| COMPILE
    COMPILE --> KNOWLEDGE
    KNOWLEDGE & COMPANION --> H_START

    DAILY & KNOWLEDGE & COMPANION --- MCP
    DAILY & KNOWLEDGE & COMPANION --- OBS
    MCP -.->|Araç Çağrıları| AGY & CUR & CLD & WND
```

Bir projeye Antigravity ile başlayıp ertesi gün Codex'e geçebilirsin. Codex, Antigravity'nin özel
sohbet ekranını veya bütün ham geçmişini devralmaz; bunun yerine ortak vault'taki son oturum,
aktif konular, kararlar, kurallar, günlük özetleri ve bilgi indeksini alır. Araç değiştirirken
taşınabilir olan şey **iş bağlamıdır**, sağlayıcının kendi sohbet arayüzü değildir.

**Respected Brain'in temel tezi şudur: hafıza rica değil, mekanizmadır.** Bir yapay zekanın
oturum biterken hafıza dosyalarını güncellemeyi hatırlamasını beklemek kırılgandır. Hatırlanmadığı her
seferde o gün kaybolur. Respected Brain'de oturum kapanışını bir kanca yakalar, konuşmayı arka planda
özetleyip `daily/` altına günlük log olarak yazar; akşamları günde bir kez bir derleyici o logları
`knowledge/` altında birbirine bağlanan makalelere dönüştürür. Ertesi sabah bu bilgi tabanının
indeksi kendiliğinden bağlama girer. Kimsenin bir şey yazmayı hatırlaması gerekmez.

Video izlemene gerek yok. Kurulum ve günlük kullanım bu README'de; ayrıntılı davranış ve bakım
notları [MULTI_AI.md](MULTI_AI.md), coding agentın uygulayacağı kurulum runbook'u [SETUP.md](SETUP.md)
içindedir.

---

## Hızlı Başlangıç: 3 Farklı Kurulum Seçeneği

Respected Brain'i ihtiyacınıza ve alışkanlığınıza en uygun kanaldan saniyeler içinde kurabilirsiniz:

### 1. AI-Native Kurulum (Önerilen — Tek Satır Prompt)

Tercih ettiğiniz kodlama asistanına (**Claude Code, Cursor Agent, Codex, Antigravity, Windsurf**) aşağıdaki tek satırlık komutu vermeniz yeterlidir:

```text
https://raw.githubusercontent.com/respected0/secondbrain/main/BOOTSTRAP.md dosyasını oku ve yönergelerine göre bu dizinde Respected Brain kasasını kur. Kuruluma başlamadan önce benden kullanıcı adımı, kasa adımı, çalışma ortamımı (Native/WSL) ve model fallback sıramı al. Bitince kurduğun tüm bileşenleri listele.
```

Asistanınız `BOOTSTRAP.md` protokolünü okur; size adınızı, kasanızın kurulacağı yeri, düşünme ortağınızın adını ve model sıralamanızı sorarak kurulumu tamamlar.

---

### 2. Tek Satır (One-Liner) Kurulum

Terminalden tek bir komutla interaktif kurulum sihirbazını başlatın:

* **Windows (PowerShell):**
  ```powershell
  irm https://raw.githubusercontent.com/respected0/secondbrain/main/install.ps1 | iex
  ```
* **Linux / macOS / WSL (Bash):**
  ```bash
  curl -sSL https://raw.githubusercontent.com/respected0/secondbrain/main/install.sh | bash
  ```

*(Sisteminizde Python veya Git yüklü değilse, sihirbaz sizi uyarır ve tek tıkla yüklemeyi teklif eder).*

---

### 3. İnteraktif CLI Kurulum Sihirbazı

Repoyu yerel makinenize klonlayıp renkli terminal sihirbazıyla kurmak isterseniz:

```bash
git clone https://github.com/respected0/secondbrain.git
cd secondbrain
python install.py
```

Sihirbaz; algılanan AI modellerini listeler, model öncelik sırasını, çalışma ortamınızı (Windows Native, WSL veya Hibrit), masaüstü Obsidian açılış kısayolunu ve sabah brifingi saatini yapılandırır.

---

### 4. Kurulumdan Sonra: Obsidian ile Açın ve Başlayın

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
  --home "/mnt/c/Users/KULLANICI" \
  --antigravity-home "/home/WSL_KULLANICISI" \
  --platform windows-wsl --providers all

# Önizleme doğruysa:
python3 scripts/install_global.py "/mnt/c/Users/KULLANICI/Documents/BenimBeynim" \
  --home "/mnt/c/Users/KULLANICI" \
  --antigravity-home "/home/WSL_KULLANICISI" \
  --platform windows-wsl --providers all --apply
```

`windows-wsl` profilinde Codex'in aktif ortak skill kopyaları çalışan WSL kullanıcısının
`~/.agents/skills/` dizinine de senkronlanır. Kurulumdan sonra Codex Desktop'ta
**Ayarlar > Hooks** bölümünden yeni veya değişmiş hook'lara güven; CLI kullanıyorsan aynı işlem
`/hooks` ekranındadır.

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
kurallarını silmez; yönetilen Respected bölümünü birleştirir ve değişecek dosyaları yedekler. Vault'un
adı serbesttir.

Antigravity IDE'yi hem Windows'ta hem **Connect to WSL** ile kullanıyorsan ek Linux profilini
`--antigravity-home` ile açıkça ver. Seçenek tekrarlanabilir; ek köklere yalnız `.gemini`
entegrasyonu kurulur, Codex/Cursor/Claude ana `--home` altında kalır. Connect to WSL kullanmıyorsan
bu seçeneği yazma.

## Dış Projelerden ve Editörlerden Erişim: Model Context Protocol (MCP)

Respected Brain, harici kod projelerinde çalışırken veya masaüstü AI editörlerini kullanırken kasanızdaki kalıcı hafızaya, kararlara ve bilgi tabanına anında erişebilmeniz için saf Python + SQLite FTS5 destekli yerel bir **Model Context Protocol (MCP)** sunucusu içerir.

### Editörlere Tek Komutla Kayıt

Aşağıdaki komutla Claude Desktop, Cursor, Antigravity IDE, Claude Code veya Windsurf editörlerine Respected Brain MCP sunucusunu otomatik olarak tanımlayabilirsiniz:

```bash
python3 scripts/vault_mcp_server.py --vault "/mutlak/vault/yolu" --register
```

Windows Native ortamında:
```powershell
py -3 scripts/vault_mcp_server.py --vault "C:\Users\KULLANICI\Documents\RespectedOS" --register
```

### Sağlanan MCP Araçları (Tools)

| Araç | Açıklama |
| :--- | :--- |
| `respected_search` | Vault içinde SQLite FTS5 tabanlı ultra hızlı anahtar kelime araması. |
| `respected_get_note` | Belirli bir not veya dokümanın tam içeriğini okur. |
| `respected_get_decisions` | Kasa genelinde alınan geçmiş mimari ve teknik kararları listeler. |
| `respected_get_companion_context` | Son oturum özeti (`Last-Session`), aktif konular (`Threads`) ve kuralları çeker. |
| `respected_quick_capture` | Dış projedeyken kasa `📥 000-Inbox/Dump/` klasörüne anında ham not düşer. |
| `respected_remember` | Önemli bir kural veya kararı doğrudan ortağın hafızasına kalıcı olarak işler. |
| `respected_expand` | Bir kavramın bilgi tabanındaki bağlantılı kavram ağını genişletir. |

## Agent değiştirmek

Ekstra taşıma komutu yoktur:

1. İlk agentın oturumunu normal biçimde bitir ve günlük özetin yazılması için birkaç saniye ver.
2. Aynı veya başka projeyi diğer agentta aç.
3. Yeni agent global/project hook üzerinden aynı vault bağlamını alır.

Örnek: Antigravity'de alınan karar kapanışta `daily/` dosyasına yazılır; Codex açıldığında son
oturum ve bilgi indeksi bağlama eklenir. Henüz kapanmamış veya özetlenmemiş son birkaç mesajın
aktarılması garanti değildir; kritik bir geçişte ilk agent oturumunu kapatmak önemlidir.

## Beyin yol haritası ve sabah brifingi

Her oturum başlangıcında model çağırmayan harita üreticisi
`🎯 100-Command-Center/Vault-Map.md` ve `Skills-Map.md` dosyalarını yeniler. `Core.md` insan
tarafından yönetilmeye devam eder. Haritalar yalnız yapı ve kanonik `.beyin/skills/` metadata'sını
kullanır; agentın bütün vault'u taramasına gerek bırakmaz.

Sabah brifingi onayla kurulan platform zamanlayıcısı tarafından yerel saat 08.00'de hazırlanır.
Kaçırılan görev Windows'ta `StartWhenAvailable`, Linux'ta persistent timer ve macOS'ta login
catch-up ile yeniden denenir. Başarılı çıktı günde bir kez
`🎯 100-Command-Center/Briefings/YYYY-MM-DD.md` yoluna yazılır ve gerçek hazırlanma saatini taşır.
Model seçimi sabit değildir; normal provider fallback zinciri kullanılır.

Kurulum önce yalnız önizleme gösterir:

```bash
python3 scripts/install_briefing_schedule.py "/mutlak/vault/yolu" \
  --home "$HOME" --platform linux
# Kontrol ettikten sonra aynı komuta --apply ekle.
```

Önizleme tam zamanlayıcı tanımını, çalışacak komutu ve hedef dosyaları gösterir. `--apply` mevcut
yönetilen tanımı değiştiriyorsa kullanıcı dizininde `.respected/schedule-backups/` altına yedek alır;
aktivasyon başarısız olursa eski tanımı geri yükler. Var olan kullanıcı yazımı `Vault-Map.md` veya
`Skills-Map.md` otomatik olarak ezilmez.

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

### 0.0.1 Öncesi Sürümlerden Güncelleme

Daha önceki (0.0.1 öncesi erken sürümlerden) bir Respected Brain kasanız varsa, repo kökünden doğrudan `scripts/update_respected.py` ile güncelleyebilirsiniz:

```bash
# 1. Önce güvenli salt-okunur önizleme:
python3 scripts/update_respected.py "/mutlak/vault/yolu"

# 2. Önizleme doğruysa uygulayın:
python3 scripts/update_respected.py "/mutlak/vault/yolu" --apply
```

(İsteğe bağlı `--force` bayrağı ile aynı sürümdeki dosyalar da yeniden eşitlenebilir).

Updater yalnız vault içindeki motor dosyalarını transaction güvenliğiyle yönetir; kişisel notlarınıza (`🔮 850-Companion`, `🧠 500-Knowledge` vb.) asla dokunmaz. Yönetilen dosyaların transaction yedeği `~/.respected/update-backups/` altında kalır.

Daha önce global bağlantı veya sabah zamanlayıcısı kurduysanız, güncellemeden sonra bunların kurucularını da (`scripts/install_global.py`, `scripts/install_briefing_schedule.py`) önce önizleme, ardından `--apply` ile yeniden çalıştırın. Böylece global kurallar ve zamanlayıcı tanımları güncellenir. Codex hook tanımı değiştiyse Desktop'ta **Ayarlar > Hooks** veya CLI'da `/hooks` üzerinden yeniden güven verin.

Bilmeniz gerekenler:
- **Hafıza klasörünün adı `🔮 850-Companion` olmak zorundadır.** Kancalar ve scriptler bu sabit yolu okur.
- **Güvenlik:** Güncelleme öncesinde git anlık görüntüsü ve transaction yedeği alınır. Herhangi bir kapı doğrulaması başarısız olursa vault eski haline geri döndürülür.
- **Sürüm damgası:** Tüm adaptör doğrulamaları ve kontroller geçtikten sonra en son `.beyin-version` tek sürüm olarak yazılır.

---

## Geleneksel Yöntemler vs Respected Brain

| | Geleneksel Sohbet / Ham Agent | Respected Brain (v0.0.1) |
| --- | --- | --- |
| Günlük hafıza | model hatırlarsa yazar | oturum kapanışında **otomatik** yazılır |
| Kanca sayısı | 0 | 4 (`session-start`, `user-prompt`, `pre-compact`, `session-end`) |
| Compaction | konuşma sıkıştırılınca kaybolur | sıkıştırma öncesi yakalanır |
| Bilgi tabanı | yok | `knowledge/` altında derlenmiş, birbirine bağlı makaleler |
| Oturum başı bağlam | son sohbet penceresi | son oturum, kurallar, son journal, bilgi indeksi, bugünün logu |
| Kalıcı kurallar | yok | `Kurallar.md`, "bunu böyle yapma" dediğinde oraya yazılır |
| Sağlık kontrolü | yok | `beyin doktor` skill'i, tek tabloda tanı |
| Eski geçmiş | yok | `geçmiş import`: ChatGPT, Claude, Gemini dışa aktarımları |
| Yükseltme | yok | yerinde, ekleme yapan, transaction korumalı |
| Bağımlılık | harici servisler | Standart Python 3; sıfır harici pip bağımlılığı |

---

## Mimari

```mermaid
sequenceDiagram
    autonumber
    participant User as 👤 Kullanıcı
    participant Agent as 🤖 AI Ajanı (Antigravity/Codex/Claude/Cursor)
    participant Hook as ⚡ Kanca (Hooks)
    participant Engine as ⚙️ flush.py / compile.py
    participant Vault as 📁 Respected Brain Vault (Markdown)

    User->>Agent: Oturum başlatır
    Agent->>Hook: session-start tetiklenir
    Hook->>Vault: Last-Session, Threads, Kurallar ve Bilgi İndeksini okur
    Hook-->>Agent: Sistem promptuna bağlamı enjekte eder
    
    User->>Agent: Çalışma & Kararlar (Sohbet / Kodlama)
    
    opt Bağlam Sıkışması
        Agent->>Hook: pre-compact tetiklenir
        Hook->>Engine: flush.py ile özet çıkar
        Engine->>Vault: daily/YYYY-MM-DD.md dosyasına oturum özeti düşer
    end

    User->>Agent: Oturumu kapatır
    Agent->>Hook: session-end tetiklenir
    Hook->>Engine: flush.py arka planda çalışır
    Engine->>Vault: daily/YYYY-MM-DD.md loguna oturum kaydedilir

    Note over Vault,Engine: Saat 18:00 sonrası veya Sabah Brifinginde
    Engine->>Vault: compile.py çalışır, logları knowledge/ makalelerine dönüştürür
```

```text
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

### Dürüst Sınırlar: Ne Yapar, Ne Yapmaz?

| Ne Yapar? (Tasarım Hedefi) | Ne Yapmaz? (Dürüst Sınırlar) |
| :--- | :--- |
| **Tam Yerel ve Açık Format:** Notların %100 düz Markdown dosyalarıdır; Obsidian veya herhangi bir metin editörüyle sonsuza kadar okunabilir. | **Kapalı Kutu / SaaS Yok:** Gizli bir bulut sunucusuna veya ücretli üçüncü parti bellek platformuna bağımlı kılmaz. |
| **Damıtılmış İş Bağlamı:** Oturumlardan kararları, kuralları, aktif konuları ve bilgi ağını aktarır. | **Bağlamı Şişirmez:** 100.000 tokenlik ham sohbet dökümünü bir sonraki oturuma yığarak modeli yavaşlatmaz ve kota yakmaz. |
| **Sıfır Bağımlılık (Zero-Dep Core):** Dış Python kütüphaneleri (`pip install` dahi gerekmez) istemez; standart Python 3 ile çalışır. | **Ağır Vektör DB Şartı Koşmaz:** Ağır embedding modelleri ve GPU gerektirmez; SQLite FTS5 ve Karpathy LLM derleyicisi kullanır. |
| **Çoklu AI Özgürlüğü:** Antigravity ile başla, Codex ile devam et, Claude Code ile test yaz. Hepsi aynı hafızaya konuşur. | **Sihirli Zihin Okuma Yapmaz:** Oturum kapanmadan önce birkaç saniyelik özet çıkarma payı bırakılmazsa o oturumun son anı `daily/` yerine insan notuna kalır. |

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
| Windows native | **Windows CI doğrulandı; gerçek iki-provider smoke bekliyor** | `py.exe -3` ile ortak Python lifecycle doğrudan çalışır; WSL/Bash gerekmez. Taze kurulum ve damgalı Respected güncellemesi desteklenir, damgasız v1 dönüşümü henüz WSL ister. |

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

### Bilgisayar kendi kendine agent veya komut penceresi açar mı?

Hayır. Arka plan işlemleri tamamen konsolsuz ve sessiz çalışır. Günlük özet oturum bitiminde
sessizce yazılır; bilgi derlemesi ise sabah 08.00 zamanlayıcısında brifing öncesinde ve
oturum başlangıçlarında kaçırılan günler için tamamlanmış-gün catch-up olarak çalışır.

## Bir şey ters giderse

Vault klasöründe kullandığın ajana `beyin doktor` yaz. Kancalar, scriptler, python3, yerel AI CLI,
günlük log tazeliği, son derleme durumu, iCloud çakışma dosyaları ve git durumu tek tabloda gelir,
her kırmızı satırın altında düzeltme komutu yazar.

---

## Credits

Bilgi derleme mimarisi Andrej Karpathy'nin LLM bilgi tabanı desenine dayanır:
https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f

Respected Brain, [Avenox Beyin](https://github.com/avenoxai/avenoxbeyin) projesinin MIT lisanslı
geçmişinden doğdu; commit geçmişini ve lisans atfını koruyarak artık bağımsız geliştiriliyor.

## Lisans

MIT, [LICENSE](LICENSE) dosyasına bak. PR'lar açık.

---

## In English (short version)

**Respected Brain** is an independently developed, provider-neutral Obsidian second brain for Claude Code, Codex, Cursor,
and Antigravity. It keeps one canonical instruction and skill source, then generates each agent's
native rules and hooks. Session-end and pre-compaction events feed conversations into `daily/`;
the selected local CLI (`claude`, `codex`, `agy`, or `cursor-agent`) compiles those logs into linked articles under
`knowledge/`. The next session starts with that knowledge index already in context.

Install: `git clone https://github.com/respected0/respectedbrain.git && cd respectedbrain`, then ask
your coding agent to read and follow `SETUP.md`. Already running a pre-0.0.1 vault?
Use `python3 scripts/update_respected.py "/path/to/vault" --apply` to update to `v0.0.1`.
Fresh vaults are initialized directly from `template/` or via `install.py` / `install.ps1` / `install.sh`.
Updates are additive only, your memory files are never touched, the settings merge is idempotent, and
updater actions are verified before execution. Two things to keep in mind: the memory folder uses the
fixed `🔮 850-Companion` path, and version stamps are written only after every validation gate passes.

Platform honesty: the original macOS path remains supported. Linux desktop remains unverified.
Windows + WSL remains verified with Windows-side hooks invoking the Python memory engine through
`wsl.exe`. Native Windows fresh install and stamped Respected updates use `py.exe -3` without WSL or
Bash. A provider-neutral global installer can connect any
named vault to Claude, Codex, Cursor and Antigravity across unrelated code repositories.

Users may switch coding agents without migrating the vault. `auto` prefers the agent that emitted
the hook; a persistent first-choice summarizer can be selected with `set_summary_provider.py`, and
retryable quota/timeout/5xx failures fall back to another installed authenticated CLI.

No extra API key is required: background work uses an authenticated local AI CLI. The core uses
the Python standard library; POSIX keeps thin Bash compatibility launchers. Knowledge-compilation
architecture credit:
Andrej Karpathy's LLM knowledge base pattern,
https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f. The project began from the
MIT-licensed history of Avenox Beyin and preserves that attribution and commit history.
