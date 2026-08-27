# Respot Brain — Güncel Mimari ve Davranış Sözleşmesi

Durum: **uygulamayla eşleşen yaşayan sözleşme**. Bu belge eski geliştirme lane'lerini değil,
`main` dalındaki güncel sistemi tarif eder. Kullanıcı kurulumu için `README.md`, agent tarafından
uygulanacak runbook için `SETUP.md`, operasyon notları için `MULTI_AI.md` yetkilidir.

## 1. Amaç ve ilkeler

Respot Brain, avenoxbeyin v2'nin otomatik hafıza hattını koruyan ve onu Claude Code'a bağlı
olmaktan çıkaran çoklu-agent forkudur. Antigravity, Codex, Cursor ve Claude Code aynı Obsidian
vault'unu kalıcı bağlam olarak kullanır. Sağlayıcıların ham sohbet ekranları taşınmaz;
`Last-Session.md`, `Threads.md`, `Kurallar.md`, `daily/` ve `knowledge/` taşınabilir sözleşmedir.

1. **Tek kaynak:** talimatlar `.beyin/instructions.md`, skill'ler `.beyin/skills/` altındadır.
2. **Provider bağımsızlığı:** coding agent ile arka plan özetleyicisi ayrı seçimlerdir.
3. **Güvenli fallback:** eksik CLI ve geçici kota/servis hatası başka kurulu CLI'a geçebilir.
4. **Yerel ve geri alınabilir:** vault Markdown'dır; yükseltme önce doğrulanmış snapshot alır.
5. **Ek API anahtarı yok:** arka plan çağrısı giriş yapılmış yerel CLI'ı kullanır.
6. **Az bağımlılık:** runtime Bash ve Python standart kütüphanesidir; pip/npm gerekmez.
7. **Dürüst platform durumu:** Windows+WSL köprüsü doğrulandı; Linux masaüstü başlatıcısı saha
   testi bekliyor; orijinal macOS akışı korunuyor.

## 2. Repo düzeni

```text
respot-brain/
├── README.md                       kullanıcı kılavuzu
├── SETUP.md                        taze kurulum ve v1 yükseltme runbook'u
├── MULTI_AI.md                     provider/global/upstream operasyonları
├── docs/
│   ├── SPEC-V2.md                  bu yaşayan sözleşme
│   ├── beyin-v2.md                 bağımsız kurulum kılavuzu
│   └── *FINDINGS*.md               tarihsel güvenlik/yükseltme kayıtları
├── scripts/
│   ├── upgrade.sh                  v1 → v2 güvenli transaction
│   ├── enable_multiai.py           mevcut v2 vault'a adapter/runtime ekleme
│   ├── render_integrations.py      tek kaynaktan agent dosyaları üretme
│   ├── install_global.py           dört agent için kullanıcı düzeyi bağlantı
│   ├── install_antigravity_global.py özel Antigravity yardımcı kurucusu
│   ├── set_summary_provider.py     vault içi kalıcı ilk tercih
│   └── upstream_sync.sh            upstream kontrol/birleştirme yardımcısı
├── template/
│   ├── .beyin/
│   │   ├── instructions.md         kanonik talimat
│   │   ├── config.json             `summary_provider`, varsayılan `auto`
│   │   ├── model_runner.py         provider seçimi ve fallback
│   │   ├── hooks/bridge.py         native payload → ortak hook payload
│   │   └── skills/*/SKILL.md       kanonik skill'ler
│   ├── AGENTS.md                   üretilmiş Codex/Cursor uyumluluğu
│   ├── CLAUDE.md                   üretilmiş Claude uyumluluğu
│   ├── .agents/                    Antigravity rules/hooks + ortak Agent Skills
│   ├── .codex/hooks.json           Codex lifecycle adapteri
│   ├── .cursor/                    Cursor rules/hooks
│   ├── .claude/                    ortak çekirdek hook ve hafıza motoru
│   ├── daily/                      makine yazımı oturum günlükleri
│   ├── knowledge/                  derlenmiş kavramlar, bağlantılar ve indeks
│   └── 🔮 850-Companion/           ilişkisel hafıza
└── tests/                           runtime, hook, upgrade ve multi-AI regresyonları
```

`.claude/` adının kalması Claude zorunluluğu anlamına gelmez. Orijinal v2 motorunun uyumluluk
konumudur; diğer native hook'lar `.beyin/hooks/bridge.py` üzerinden aynı motoru çağırır.

## 3. Tek kaynak ve üretim

Elle düzenlenen kanonik dosyalar `template/.beyin/instructions.md` ve
`template/.beyin/skills/<skill>/SKILL.md` dosyalarıdır. Bunlardan şu adapterlar üretilir:

- `template/AGENTS.md` ve `template/CLAUDE.md`
- `template/.agents/rules/beyin.md`
- `template/.cursor/rules/beyin.mdc`
- `.agents/skills/` ve `.claude/skills/`
- agent hook JSON dosyaları
- `template/scripts/` altındaki dağıtım kopyaları

```bash
python3 scripts/render_integrations.py
python3 scripts/render_integrations.py --check
```

Üretilmiş dosya doğrudan düzenlenmez. Değişiklik kanonik kaynağa yapılır ve yeniden üretilir.

## 4. Agent adapter sözleşmesi

| Agent | Talimat | Skill keşfi | Native olaylar | Arka plan CLI |
| --- | --- | --- | --- | --- |
| Antigravity | `.agents/rules/beyin.md` | `.agents/skills/` | `PreInvocation`, `Stop` | `agy` |
| Codex | `AGENTS.md` | `.agents/skills/` | başlangıç, prompt, kapanış, pre-compact | `codex exec` |
| Cursor | `.cursor/rules/beyin.mdc`, `AGENTS.md` | `.agents/skills/` | başlangıç, prompt, kapanış, pre-compact | `cursor-agent -p` |
| Claude | `CLAUDE.md` | `.claude/skills/` | başlangıç, prompt, kapanış, pre-compact | `claude -p` |

Köprü session kimliği, transkript yolu, cwd/workspace, model ve provider alanlarını normalize eder.
Windows yolları WSL yoluna çevrilir. Global hook vault içinden tetiklenmişse proje hook'uyla çift
çalışması önlenir. Antigravity `PreInvocation` yalnız ilk invocation'da başlangıç sayılır.

## 5. Hafıza yaşam döngüsü

```text
native agent olayı
       ↓
.beyin/hooks/bridge.py
       ↓
.claude/hooks/*.sh
       ↓
flush.py → daily/YYYY-MM-DD.md
       ↓  18:00 sonrası ilk uygun kapanış, değişen log varsa
compile.py → knowledge/concepts + connections + index + log
       ↓
sonraki agent başlangıcında ortak bağlam enjeksiyonu
```

Başlangıç katmanı `Last-Session.md`, aktif `Threads.md`, `Kurallar.md` ilk 60 satır, son Journal
girişi, bilgi indeksi ve bugün/yoksa dün yazılan daily kuyruğunu enjekte eder. Toplam bağlam üst
sınırı 16.000 karakterdir; önce indeks, sonra günlük kırpılır, ilişkisel çekirdek korunur.

Kapanış/pre-compact hook'u stdin'i state altında geçici dosyaya alır ve `flush.py` sürecini arka
planda başlatıp hızlı döner. Transkript providera göre normalize edilir. Beş sabit Türkçe bölümden
oluşmayan, boş veya şüpheli özet reddedilir. Aynı session için eşzamanlı çağrılar kilit/dedup ile
tek kayda indirilir.

Saat 18:00 bir zamanlayıcı değildir. 18:00'den sonraki ilk uygun oturum kapanışında değişmiş daily
girdisi varsa compile tetiklenir; sistem kendi kendine IDE veya ChatGPT açmaz.

Derleme geçici staging ağacında yapılır. Yalnız `knowledge/index.md`, `knowledge/log.md`,
`knowledge/concepts/*.md` ve `knowledge/connections/*.md` doğrulanıp vault'a taşınabilir. Silme,
symlink, izin verilmeyen yol veya beklenmeyen fark reddedilir. Başarılı doğrulamadan önce daily
hash'i ingested sayılmaz.

## 6. Provider seçimi ve fallback

Varsayılan `.beyin/config.json`:

```json
{
  "summary_provider": "auto"
}
```

`auto`, önce hook'u üreten agentın providerını, sonra kalan kurulu providerları dener. Kalıcı ilk
tercih seçilmişse o provider ilk sıraya alınır; coding agent sabitlenmez.

Fallback yapılan durumlar: executable bulunamaması, timeout/process hatası, quota/rate-limit/429,
geçici kapasite ve 502/503/504 sınıfı servis hataları. Kimlik doğrulama veya kalıcı yapılandırma
hatası görünür biçimde durur. `BEYIN_MODEL_PROVIDER` geçici ortam override'ıdır.
`BEYIN_LLM_COMMAND` ise prompt'u stdin'den alan tam özel-komut override'ıdır.

## 7. Kurulum sözleşmeleri

### Taze kurulum

Agent `SETUP.md` dosyasını tamamen okur; kullanıcı, companion, vault adı/yolu, opsiyonel kapsamlar,
mem0, agentlar ve global bağlantı tercihlerini sorar. Template kopyalanır, placeholderlar çözülür,
adapterlar üretilir, git snapshot alınır ve doktor kontrolü yapılır.

### v1 yükseltmesi

`scripts/upgrade.sh` mutlak `--vault` alır. `check`, `apply`, `finalize` ayrı süreçlerde güvenle
çalışır. Repo kökü, `/`, göreli hedef ve işaretsiz klasör reddedilir. Kullanıcı hafızası üzerine
yazılmaz. Snapshot doğrulanmadan mutasyon başlamaz; `.beyin-version` son atomik yazıdır. Ardından
`enable_multiai.py` provider adapterlarını ekler.

### Global bağlantı

`install_global.py` adı serbest vault'u seçilen providerlara kullanıcı düzeyinde bağlar. Varsayılan
preview'dür; `--apply` açık onaydan sonra verilir. Mevcut global kurallar/hook'lar korunur, Respot
yönetim bloğu idempotent birleştirilir ve değişen dosyalar yedeklenir.

## 8. Platform sözleşmesi

- **Windows + WSL:** Windows IDE hook'u `wsl.exe --cd <vault>` ile WSL Python runtime'ını çağırır.
  Vault `/mnt/<drive>/...` altındadır; Obsidian aynı klasörü Windows yolundan açabilir.
- **macOS:** orijinal Bash/Python motoru ve isteğe bağlı `.app` başlatıcı korunur.
- **Linux:** runtime taşınabilirdir; XDG `.desktop` yolu vardır, masaüstü saha testi beklemektedir.

## 9. Güvenlik ve veri sınırı

- Transkript ve daily metni güvenilmeyen veri kabul edilir.
- Model komutları shell stringiyle değil argv listesiyle çalıştırılır.
- Flush modeline yazma aracı verilmez ve çıktı şeması doğrulanır.
- Compile staging ve allow-list doğrulaması olmadan vault'a yazamaz.
- Secret local settings/yedekleri gitignore ve staging kapılarıyla korunur.
- Upgrade secret geçmişini otomatik yeniden yazmaz; izlenen secret bulursa rotasyon uyarısı verir.
- Geçmiş import, arşivi okumadan ve daily yazmadan önce iki açık onay kapısı uygular.

Tarihsel bulgular `docs/GATE-REVIEW-SECURITY.md` içinde korunur; üst durum notu güncel çözümü ve
regresyon testlerini belirtir.

## 10. Test ve yayın kapısı

```bash
python3 scripts/render_integrations.py --check
python3 -m unittest -v tests/scripts_test.py tests/multiai_test.py
bash tests/hooks_test.sh
bash tests/upgrade_settings_test.sh
bash tests/upgrade_transaction_test.sh
git diff --check
```

Testler gerçek model/ağ çağrısı yapmaz. Provider stub'larıyla eşzamanlılık, hostile input,
allow-list, quota fallback, global kurucu idempotency'si, Windows yol köprüsü ve upgrade transaction
kapıları temp vault'larda doğrulanır.

## 11. Upstream politikası

Orijinal `avenoxai/avenoxbeyin` upstream kaynağıdır. `upstream_sync.sh check` farkları listeler;
`merge` temiz worktree ve geri dönüş dalı ister, commit etmeden birleştirmeyi bırakır. Upstream
değişikliği provider-neutral sözleşmeyi, staging güvenliğini veya kullanıcı hafızası kapılarını
atlayamaz.

## 12. İsim ve sürüm

- Proje/fork: **Respot Brain**
- Vault adı: kullanıcı seçer; `respectedOS` zorunlu değildir.
- Companion adı: kullanıcı seçer; `Respot` zorunlu değildir.
- Çekirdek damgası: `.beyin-version = 2.0.0`
- Multi-AI damgası: `.beyin-multi-version = 1.0.0`
- Sabit iç hafıza yolu: `🔮 850-Companion/`

Orijinal proje ve Avenox atfı korunur; yetkili fork kurulum adresi
`https://github.com/respected0/respot-brain` olur.
