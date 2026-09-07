# Respected Brain — Sistem Mimarisi ve Tasarım Kılavuzu

Durum: **Yetkili Mimari Kılavuz (Golden Standard)**<br>
Kaynak: `https://github.com/respected0/respectedbrain`

Respected Brain; Antigravity, Codex, Cursor ve Claude Code araçlarını yerel bir Obsidian Markdown vault'u etrafında birleştiren, bağımsız ve provider-neutral bir yapay zeka hafıza katmanıdır. Herhangi bir harici cloud bağımlılığı, merkezi veritabanı veya ek API anahtarı gerektirmez.

---

## 1. Mimari Vizyon ve Temel İlkeler

Farklı yapay zeka araçlarıyla çalışırken en büyük problem **bağlam kopukluğudur**: Bir kodlama aracında verilen kararlar, çözülen hatalar veya belirlenen mimari kurallar diğer araçlar tarafından bilinmez. Respected Brain bu problemi yerel dosya sistemi üzerinde çalışan ortak bir hafıza döngüsü ile çözer.

```text
┌─────────────────────────────────────────────────────────────┐
│                 Coding & Research Agentları                 │
│      Antigravity    •    Codex    •    Cursor    •   Claude     │
└──────────────┬───────────────────────────────▲──────────────┘
               │ (PreInvocation / Stop)        │ (SessionStart)
               ▼                               │
       ┌───────────────┐               ┌───────┴──────┐
       │ bridge.py     │               │ Ortak Bağlam │
       │ (Normalizer)  │               │ Enjeksiyonu  │
       └───────┬───────┘               └───────▲──────┘
               ▼                               │
       ┌───────────────┐               ┌───────┴──────┐
       │ flush.py      │               │ Vault/Skills │
       │ (Arka Plan)   │               │ Haritaları   │
       └───────┬───────┘               └───────▲──────┘
               ▼                               │
       ┌───────────────┐               ┌───────┴──────┐
       │ daily/*.md    │──────────────►│ compile.py   │
       │ Günlük Log    │               │ (Staging'de) │
       └───────────────┘               └───────▲──────┘
                                               │
                                       ┌───────┴──────┐
                                       │ knowledge/   │
                                       │ Kavramlar &  │
                                       │ İndeks       │
                                       └──────────────┘
```

### Temel Tasarım İlkeleri

1. **Tek Doğruluk Kaynağı (SSOT):** Tüm kurallar ve çalışma talimatları `template/.beyin/instructions.md` dosyasında, yetenekler ise `template/.beyin/skills/` altında tutulur. Agent yapılandırmaları bu kaynaktan otomatik üretilir.
2. **Sağlayıcı Bağımsızlığı (Provider-Neutral):** Kodlama yaptığınız agent (örn. Antigravity) ile arka planda hafıza özetini çıkaran CLI (örn. Codex) birbirinden bağımsızdır.
3. **Sıfır Ek Maliyet & Ek Anahtar Yok:** Sistem kendi başına ücretli bir API anahtarı istemez; geliştiricinin makinesinde kurulu ve oturum açmış yerel CLI araçlarının (`agy`, `codex`, `cursor-agent`, `claude`) mevcut oturumlarını kullanır.
4. **Dayanıklı Fallback Mimarisi:** Oturumu kapatan agent'ın CLI'ı yanıt vermezse, kota aşımı (429) veya servis hatası (502/503/504) verirse, sistem otomatik olarak kurulu diğer hazır CLI'a geçer.
5. **Yerel Dosya Bütünlüğü & Geri Alınabilirlik:** Tüm veriler standart Markdown dosyalarıdır. Veri kaybına karşı otomatik Git snapshot'ları ve Restic desteği bulunur.
6. **Güvenli Sınırlar (Zero-Trust):** Transkript ve günlük metinleri potansiyel olarak düşmanca (untrusted) kabul edilir. Derleme izole staging dizininde yapılır; model komutları shell injection riskine karşı her zaman doğrudan argüman dizileri (`argv`) ile çalıştırılır.

---

## 2. Ne Taşınır, Ne Taşınmaz?

| Kategori | Taşınan / Ortak Hafızaya Giren | Taşınmayan / Yerelde Kalan |
| --- | --- | --- |
| **Hafıza & Durum** | Son oturum özeti (`Last-Session.md`), aktif konular (`Threads.md`), günlük kurallar (`Kurallar.md`). | Agent IDE pencerelerindeki ham sohbet geçmişi ve UI durumları. |
| **Bilgi Tabanı** | Yapılandırılmış oturum kayıtları (`daily/`), derlenmiş kavramlar ve bağlantılar (`knowledge/`). | Kapanmamış/flush edilmemiş anlık komut çıktıları ve geçici terminal tamponları. |
| **Yetenekler** | Kanonik agent skill'leri (`beyin-doktor`, `inbox-duzenle`, `yazilim-kalite` vb.). | Giriş yapılmamış bir sağlayıcının hesabı, kotası veya token'ı. |

---

## 3. Dizin Yapısı ve Çekirdek Bileşenler

```text
respectedbrain/
├── README.md                       # Kullanıcı genel tanıtımı ve hızlı başlangıç
├── SETUP.md                        # Adım adım kurulum ve operasyon runbook'u
├── SETUP-WINDOWS.md                # Native Windows PowerShell kurulum kılavuzu
├── MULTI_AI.md                     # Çoklu-AI operasyonları, model ve CLI yönetimi
├── docs/                           # Canlı teknik dökümantasyon
│   ├── ARCHITECTURE.md             # Bu mimari ve sistem tasarımı kılavuzu
│   ├── SPECIFICATION.md            # Teknik spesifikasyon ve davranış sözleşmesi
│   └── SECURITY.md                 # Zero-Trust güvenlik ve tehdit modeli
├── scripts/                        # Yönetim, güncelleme ve CLI araçları
│   ├── update_respected.py         # Transactional vault güncelleme motoru
│   ├── enable_multiai.py           # Çoklu-AI katmanı onarım/entegrasyon aracı
│   ├── render_integrations.py      # SSOT'tan agent adaptörlerini üreten motor
│   ├── install_global.py           # Kullanıcı düzeyinde global vault bağlayıcı
│   ├── install_briefing_schedule.py# Sabah 08:00 zamanlayıcı kurulum aracı
│   ├── set_summary_provider.py     # Kalıcı özetleyici sağlayıcı yapılandırıcısı
│   └── url_safety.py               # SSRF ve güvenli ağ istekleri kütüphanesi
├── template/                       # Vault iskeleti ve çekirdek motor
│   ├── .beyin/                     # Çekirdek motor ve SSOT
│   │   ├── instructions.md         # Kanonik talimatlar (SSOT)
│   │   ├── config.json             # Runtime yapılandırması (`summary_provider`)
│   │   ├── engine/                 # Arka plan motorları
│   │   │   ├── flush.py            # Oturum kapanış özetleyicisi
│   │   │   └── compile.py          # Staging'de izole bilgi tabanı derleyicisi
│   │   ├── hooks/                  # Yaşam döngüsü köprüleri
│   │   │   ├── bridge.py           # Ortak olay normalizasyonu ve yönlendirme
│   │   │   └── lifecycle.py        # Hook olay işleyicileri
│   │   ├── model_runner.py         # CLI yürütücü ve otomatik fallback motoru
│   │   ├── map_builder.py          # Hızlı Vault-Map ve Skills-Map üretici
│   │   ├── morning_briefing.py     # Sabah 08:00 brifing motoru
│   │   ├── graph_analysis.py       # Not bağlantıları ve graph analitiği
│   │   ├── bounded_recall.py       # Bounded bağlam kırpma ve geri çağırma
│   │   └── skills/                 # Kanonik yetenekler (SSOT)
│   ├── AGENTS.md                   # Codex / Cursor ortak talimat adaptörü
│   ├── CLAUDE.md                   # Claude Code talimat adaptörü
│   ├── .agents/                    # Antigravity kuralları ve hook'ları
│   ├── .cursor/                    # Cursor kuralları ve hook'ları
│   ├── .codex/                     # Codex hooks.json tanımları
│   ├── daily/                      # Otomatik oluşturulan günlük kayıtlar
│   ├── knowledge/                  # Derlenmiş kavramlar, bağlantılar ve indeks
│   └── 🔮 850-Companion/           # İnsan-AI ilişkisel çekirdek hafızası
└── tests/                          # 100% kapsamlı regression ve contract testleri
```

---

## 4. Tek Doğruluk Kaynağı (SSOT) ve Entegrasyon Motoru

Agent'lar farklı dosya adları ve biçimleri bekler:
- **Antigravity:** `.agents/rules/beyin.md` ve `.agents/skills/`
- **Codex:** `AGENTS.md` ve `.agents/skills/`
- **Cursor:** `.cursor/rules/beyin.mdc`, `AGENTS.md` ve `.agents/skills/`
- **Claude Code:** `CLAUDE.md` ve `.claude/skills/`

Bu dosyaları ayrı ayrı elle düzenlemek çelişkilere ve sürüklenmeye (drift) yol açar. Respected Brain mimarisinde:
1. Geliştirici yalnızca `template/.beyin/instructions.md` ve `template/.beyin/skills/*/SKILL.md` dosyalarını düzenler.
2. `scripts/render_integrations.py` çalıştırılarak tüm agent kuralları, hook tanımları ve skill sembolik linkleri/kopyaları deterministik olarak türetilir.
3. Test kapısında (`python3 scripts/render_integrations.py --check`) hiçbir üretilmiş dosyanın el ile tahrif edilmediği doğrulanır.

---

## 5. Çekirdek Hafıza Yaşam Döngüsü

### Aşama 1: Oturum Başlangıcı (Session Start & Ingestion)
Agent bir projede veya vault içinde açıldığında:
1. `bridge.py` tetiklenir ve `map_builder.py` çağrılır.
2. `Vault-Map.md` ve `Skills-Map.md` dosyaları metadata taranarak hızlıca yenilenir (not gövdeleri okunmaz, saniyeler içinde tamamlanır).
3. `Last-Session.md`, aktif `Threads.md`, `Kurallar.md` dosyasının ilk 60 satırı, son Journal girdisi, bilgi indeksi ve günün daily kuyruğu birleştirilir.
4. Toplam bağlam **16.000 karakterlik üst sınırla (bounded context)** sınırlandırılır. Token şişmesini engellemek için önce indeks, sonra günlükler güvenli biçimde kırpılır; ilişkisel çekirdek daima korunur.

### Aşama 2: Oturum Kapanışı ve Flush (Session End / Stop / Pre-Compact)
Oturum bittiğinde veya bağlam sıkıştırma (pre-compact) gerektiğinde:
1. Native hook olayından gelen transkript yolu veya stdin verisi yakalanır.
2. `flush.py` arka planda bağımsız bir süreç olarak başlatılır ve ana agent IDE'yi bloke etmeden milisaniyeler içinde kullanıcıya döner.
3. Transkript sağlayıcıya göre normalize edilir; CLI üzerinden model çalıştırılarak şu 5 sabit Türkçe başlıkta özet üretilir:
   - `## 1. Oturum Özeti`
   - `## 2. Alınan Kararlar`
   - `## 3. Yapılan Değişiklikler`
   - `## 4. Karşılaşılan Sorunlar ve Çözümler`
   - `## 5. Sonraki Adımlar ve Açık Kalan Konular`
4. Bu 5 bölümü eksiksiz içermeyen, boş veya hatalı çıktılar reddedilir.
5. Geçerli özet `daily/YYYY-MM-DD.md` dosyasına atomik kilit (file lock) ve deduplication korumasıyla eklenir.

### Aşama 3: Bilgi Tabanı Derlemesi (Compilation)
Günlük oturum özetlerinin kalıcı bilgiye dönüştürülmesi:
- Zamanlanmış sabah brifingi pipeline'ı (`morning_briefing.py`) veya SessionStart sırasında kaçırılmış günler için tetiklenen catch-up mekanizması (`compile.py`) çalışır.
- Gün içinde devam eden oturumların daily dosyaları erken derlenmez (`--before-date` sınırı).
- Derleme işlemi doğrudan vault içinde değil, **işletim sisteminin `0700` izinli geçici bir staging dizininde** izole olarak çalıştırılır.
- Staging çıktısı taranarak yalnızca izin verilen dosya yolları (`knowledge/index.md`, `knowledge/log.md`, `knowledge/concepts/*.md`, `knowledge/connections/*.md`) vault'a atomik olarak aktarılır.
- Symlink'ler, beklenmeyen dosya silmeleri veya izin verilmeyen yollar reddedilir.

### Aşama 4: Sabah Brifingi (Morning Briefing)
Her sabah 08:00'de zamanlayıcı (Windows Task Scheduler, systemd timer veya LaunchAgent) çalışır:
1. `morning_briefing.py --if-due` komutu önce `compile.py` ile bilgi tabanını günceller.
2. Önceki günlerin kararlarını, açık thread'leri ve proje durumlarını özetler.
3. `🎯 100-Command-Center/Briefings/YYYY-MM-DD.md` dosyasını oluşturur ve `Dashboard.md` içindeki işaretli yönetim bloğunu atomik olarak günceller.
4. Gün içinde tekrar çalışırsa aynı gün için birden fazla dosya üretmez (idempotent).

---

## 6. Sağlayıcı Seçimi ve Otomatik Fallback Matrisi

`.beyin/config.json` içindeki varsayılan yapılandırma:

```json
{
  "summary_provider": "auto"
}
```

`model_runner.py` şu stratejiye göre çalışır:
1. `auto` modu: Oturumu kapatan agent'ın kendi CLI'ını ilk sıraya koyar.
2. CLI bulunamazsa, süreç zaman aşımına uğrarsa, HTTP 429 / kota sınırı alınırsa veya 502/503/504 servis hatası gerçekleşirse sistem durmaz; kurulu ve giriş yapılmış diğer CLI'a geçer.
3. Yetkilendirme (auth) veya kalıcı sözdizimi hatalarında ise sessizce başka sağlayıcıya geçilmez; hata geliştiriciye bildirilir.
4. İstenirse kullanıcı `scripts/set_summary_provider.py` ile kalıcı bir tercih (`antigravity`, `codex`, `cursor`, `claude`) belirleyebilir.

```text
┌─────────────────────────────────────────────────────────────┐
│                       model_runner.py                       │
└──────────────────────────────┬──────────────────────────────┘
                               │
            ┌──────────────────┴──────────────────┐
            ▼                                     ▼
   [auto] Aktif CLI                      [Kalıcı İlk Tercih]
   (Antigravity / Codex / ...)           (Kullanıcının seçimi)
            │                                     │
            ├─ Başarılı ──────────────────────────┤
            │                                     │
            └─ Hata (429 / 503 / Timeout)         │
                     │                            │
                     ▼                            ▼
            [Fallback Zinciri: Diğer Hazır CLI'lar]
            (agy -> codex -> cursor-agent -> claude)
```

---

## 7. Platform Çalışma Profilleri

Respected Brain üç ana platform profilini birinci sınıf vatandaş olarak destekler:

1. **`windows-wsl` (Windows + WSL):**
   - Windows IDE'leri hook tetiklendiğinde `wsl.exe --cd <vault>` aracılığıyla WSL ortamındaki Python runtime'ını çağırır.
   - Vault `/mnt/c/...` altındadır; Obsidian aynı dizini doğrudan Windows üzerinden açar.
2. **`windows-native` (Native Windows):**
   - WSL, Bash veya POSIX emülasyonu gerektirmez.
   - `py.exe -3` mutlak Windows yollarıyla `C:\...\.beyin\hooks\bridge.py` dosyasını çalıştırır.
   - `install-windows.ps1` PowerShell üzerinden ortamı doğrular ve kurulumu tamamlar.
3. **`portable` (macOS & Linux):**
   - Standart POSIX dosya sistemi ve sistem Python 3'ü ile çalışır.
   - Linux masaüstü için XDG `.desktop` entegrasyonu, macOS için LaunchAgent zamanlayıcısı mevcuttur.

---

## 8. Güvenlik ve Doğrulama Standartları

- **Claude zorunlu değildir:** Tüm sistem tamamen bağımsız çalışır; geliştirici dilediği AI aracı kombinasyonunu kullanabilir.
- **Damgasız v1 ve Geçmiş Vault Uyumluluğu:** 1.0.0 ile 1.4.5 arasındaki tüm damgalı vault'lar `scripts/update_respected.py` ile transactional olarak güncellenebilir.
- **Yedekleme Güvencesi:** Yükseltme öncesinde doğrulanmış Git snapshot'ları ve Restic entegrasyonu (`scripts/backup_restic.py`) ile tam geri dönülebilirlik sağlanır.
- **Zero-Trust Güvenlik:** Ayrıntılı güvenlik politikaları, SSRF filtreleri ve staging izolasyonu için [docs/SECURITY.md](file:///c:/Users/Furkan/Documents/ChatGPT/secondbrain/docs/SECURITY.md) belgesine bakın.
- **Teknik Sözleşmeler:** Kesin manifest ve davranış kuralları için [docs/SPECIFICATION.md](file:///c:/Users/Furkan/Documents/ChatGPT/secondbrain/docs/SPECIFICATION.md) belgesine bakın.
