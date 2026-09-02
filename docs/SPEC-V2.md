# Respected Brain — Güncel Mimari ve Davranış Sözleşmesi

Durum: **uygulamayla eşleşen yaşayan sözleşme**. Bu belge eski geliştirme lane'lerini değil,
`main` dalındaki güncel sistemi tarif eder. Kullanıcı kurulumu için `README.md`, agent tarafından
uygulanacak runbook için `SETUP.md`, operasyon notları için `MULTI_AI.md` yetkilidir.

## 1. Amaç ve ilkeler

Respected Brain, avenoxbeyin v2'nin MIT lisanslı otomatik hafıza geçmişinden doğmuş ve onu Claude
Code'a bağlı olmaktan çıkaran bağımsız çoklu-agent projesidir. Antigravity, Codex, Cursor ve Claude Code aynı Obsidian
vault'unu kalıcı bağlam olarak kullanır. Sağlayıcıların ham sohbet ekranları taşınmaz;
`Last-Session.md`, `Threads.md`, `Kurallar.md`, `daily/` ve `knowledge/` taşınabilir sözleşmedir.

1. **Tek kaynak:** talimatlar `.beyin/instructions.md`, skill'ler `.beyin/skills/` altındadır.
2. **Provider bağımsızlığı:** coding agent ile arka plan özetleyicisi ayrı seçimlerdir.
3. **Güvenli fallback:** eksik CLI ve geçici kota/servis hatası başka kurulu CLI'a geçebilir.
4. **Yerel ve geri alınabilir:** vault Markdown'dır; yükseltme önce doğrulanmış snapshot alır.
5. **Ek API anahtarı yok:** arka plan çağrısı giriş yapılmış yerel CLI'ı kullanır.
6. **Az bağımlılık:** kanonik runtime Python standart kütüphanesidir; POSIX Bash dosyaları ince
   uyumluluk launcherlarıdır, pip/npm gerekmez.
7. **Dürüst platform durumu:** Windows+WSL korunur; native Windows gerçek PowerShell/Python süreç
   testlerinden geçer; Linux masaüstü başlatıcısı saha testi bekler; orijinal macOS akışı korunur.

## 2. Repo düzeni

```text
respectedbrain/
├── README.md                       kullanıcı kılavuzu
├── SETUP.md                        taze kurulum ve v1 yükseltme runbook'u
├── MULTI_AI.md                     provider/global/upstream operasyonları
├── docs/
│   ├── SPEC-V2.md                  bu yaşayan sözleşme
│   ├── beyin-v2.md                 bağımsız kurulum kılavuzu
│   └── *FINDINGS*.md               tarihsel güvenlik/yükseltme kayıtları
├── scripts/
│   ├── upgrade.sh                  v1/çekirdek-v2 → Respected güvenli transaction
│   ├── enable_multiai.py           bağımsız v2 onarımı/adapter-runtime ekleme
│   ├── render_integrations.py      tek kaynaktan agent dosyaları üretme
│   ├── install_briefing_schedule.py 08:00 platform zamanlayıcısı preview/apply
│   ├── install_global.py           dört agent için kullanıcı düzeyi bağlantı
│   ├── install_antigravity_global.py özel Antigravity yardımcı kurucusu
│   ├── set_summary_provider.py     vault içi kalıcı ilk tercih
│   └── upstream_sync.sh            upstream kontrol/birleştirme yardımcısı
├── template/
│   ├── .beyin/
│   │   ├── instructions.md         kanonik talimat
│   │   ├── config.json             `summary_provider`, varsayılan `auto`
│   │   ├── model_runner.py         provider seçimi ve fallback
│   │   ├── map_builder.py          görünür Vault/Skills haritaları
│   │   ├── morning_briefing.py     günde tek doğrulanmış brifing
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
       ↓  18:00 sonrası kapanış veya sonraki başlangıçta tamamlanmış-gün catch-up
compile.py → knowledge/concepts + connections + index + log
       ↓
sonraki agent başlangıcında ortak bağlam enjeksiyonu
```

Başlangıç katmanı önce görünür `Vault-Map.md` ve `Skills-Map.md` dosyalarını metadata'dan yeniler;
not gövdelerini topluca okumaz. Ardından `Last-Session.md`, aktif `Threads.md`, `Kurallar.md` ilk
60 satır, son Journal girişi, iki harita, bilgi indeksi ve bugün/yoksa dün yazılan daily kuyruğunu
enjekte eder. Toplam bağlam üst sınırı 16.000 karakterdir; önce indeks, sonra günlük kırpılır,
ilişkisel çekirdek korunur. `Core.md` yalnız insan tarafından yönetilen kimlik kaynağıdır.
Harita dosyaları üretici işaretiyle sahiplenilir; aynı yolda kullanıcı yazımı dosya varsa veya yol
symlink/reparse üzerinden vault dışına çıkıyorsa yenileme fail-closed durur ve dosyayı korur.

Kapanış/pre-compact hook'u stdin'i state altında geçici dosyaya alır ve `flush.py` sürecini arka
planda başlatıp hızlı döner. Transkript providera göre normalize edilir. Beş sabit Türkçe bölümden
oluşmayan, boş veya şüpheli özet reddedilir. Aynı session için eşzamanlı çağrılar kilit/dedup ile
tek kayda indirilir.

Saat 18:00 bir zamanlayıcı değildir. 18:00'den sonraki ilk uygun oturum kapanışında değişmiş daily
girdisi varsa compile tetiklenir; sistem kendi kendine IDE veya ChatGPT açmaz. Bu kapanış hiç
olmazsa sonraki SessionStart, yalnız tarihi bitmiş daily girdileri için ayrık catch-up başlatır.
İçinde bulunulan gün `--before-date` sınırıyla dışarıda tutulur. Başarılı veya başarısız her compile
tetik claim'ini bırakır; aynı günün sonraki geçerli tetikleri bloke edilmez.

Derleme vault ve `.claude/` dışında, işletim sisteminin rastgele `0700` geçici dizininde yapılır.
Yalnız `knowledge/index.md`, `knowledge/log.md`,
`knowledge/concepts/*.md` ve `knowledge/connections/*.md` doğrulanıp vault'a taşınabilir. Silme,
symlink, izin verilmeyen yol veya beklenmeyen fark reddedilir. Başarılı doğrulamadan önce daily
hash'i ingested sayılmaz; staging başarıda ve hatada temizlenir.

## 6. Sabah brifingi ve bakım sözleşmesi

`morning_briefing.py --if-due` yerel saat 08.00'den önce salt-okunur no-op'tur. Sonrasında yalnız
tamamlanmış bounded kaynakları provider-neutral `model_runner.py` ile özetler; aynı tarih için kilit
ve final-dosya kontrolü en çok bir başarılı çıktı üretir. Çıktı
`🎯 100-Command-Center/Briefings/YYYY-MM-DD.md` yoluna gerçek `prepared_at` saatiyle atomik yazılır
ve Dashboard yalnız işaretli yönetim bloğunda güncellenir. Hata final üretmez ve aynı gün yeniden
denenebilir.

`install_briefing_schedule.py` varsayılan olarak salt-okunur önizlemedir; `--apply` ancak açık
kullanıcı onayıyla Windows Task Scheduler, WSL üzerinden Task Scheduler, Linux user systemd timer
veya macOS LaunchAgent kurar. Windows `StartWhenAvailable`, Linux `Persistent=true`, macOS
`RunAtLoad` ile kaçırılan çalışmayı yakalar. Önizleme tam tanım/komut/hedefleri gösterir; değişen
yönetilen tanımlar kullanıcı home'unda yedeklenir ve aktivasyon hatasında geri alınır. Kurulum
Python ve provider arama yolunu açıkça taşır ama provider/model sabitlemez.

`beyin-doktor` bozuk bağlantı, tekrar, bayat bilgi, bekleyen not ve mekanik sorunlar için numaralı
bir düzeltme planı çıkarır ama değiştirmez. `inbox-duzenle`, `📥 000-Inbox/Dump/` notları için hedef,
başlık, etiket ve bağlantı önizlemesi ile kaynak hash'i gösterir; yalnız kullanıcının seçtiği plan
kimliklerini hash'i yeniden doğruladıktan sonra uygular. Silme, üzerine yazma ve onaysız taşıma yoktur.

## 7. Provider seçimi ve fallback

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

## 8. Kurulum sözleşmeleri

### Taze kurulum

Agent `SETUP.md` dosyasını tamamen okur; kullanıcı, companion, vault adı/yolu, opsiyonel kapsamlar,
mem0, agentlar ve global bağlantı tercihlerini sorar. Template kopyalanır, placeholderlar çözülür,
adapterlar üretilir, git snapshot alınır ve doktor kontrolü yapılır.

### v1 yükseltmesi

`scripts/upgrade.sh` mutlak `--vault` alır. `check`, `apply`, `finalize` ayrı süreçlerde güvenle
çalışır. Repo kökü, `/`, göreli hedef ve işaretsiz klasör reddedilir. Kullanıcı hafızası üzerine
yazılmaz. Snapshot doğrulanmadan mutasyon başlamaz. `apply`, çekirdek dosyalarla birlikte
`enable_multiai.py --defer-version-stamp` üzerinden tek-kaynak talimatları ve dört provider
adapterını kurar. `finalize` adapter drift'ini ve bütün kapıları yeniden doğrular; önce
`.beyin-multi-version`, sonra işlemin yetkili son yazısı olarak `.beyin-version` damgasını koyar.
Yalnız çekirdek `2.0.0` damgası bulunan vault tamamlanmış sayılmaz; aynı işlem Respected katmanını
ekleyerek yükseltmeyi bitirir.

### Global bağlantı

`install_global.py` adı serbest vault'u seçilen providerlara kullanıcı düzeyinde bağlar. Varsayılan
preview'dür; `--apply` açık onaydan sonra verilir. Mevcut global kurallar/hook'lar korunur, Respected
yönetim bloğu idempotent birleştirilir ve değişen dosyalar yedeklenir.

### Native Windows taze kurulum ve update

`install-windows.ps1`, hedefe dokunmadan önce gerçek Python 3, Git ve kullanıcı tarafından seçilen
provider CLI'larını çalıştırarak doğrular. Claude zorunlu değildir. Dolu hedef exit `3` ile aynen
korunur; temiz hedef `windows-native` profiliyle `2.0.0` / `1.3.0` damgalanır. Mevcut damgalı
Respected vault `update_respected.py --platform windows-native` ile transactional güncellenir. Damgasız
v1 native dönüşümü reddedilir ve WSL upgrade yolu kullanılır.

## 9. Platform sözleşmesi

- **Windows + WSL:** Windows IDE hook'u `wsl.exe --cd <vault>` ile WSL Python runtime'ını çağırır.
  Vault `/mnt/<drive>/...` altındadır; Obsidian aynı klasörü Windows yolundan açabilir.
- **Windows native:** `py.exe -3` mutlak `C:\...\.beyin\hooks\bridge.py` yolunu çağırır. Dört
  provider aynı Python lifecycle'ı kullanır; WSL, Bash ve POSIX vault yolu gerekmez.
- **macOS:** orijinal Bash/Python motoru ve isteğe bağlı `.app` başlatıcı korunur.
- **Linux:** runtime taşınabilirdir; XDG `.desktop` yolu vardır, masaüstü saha testi beklemektedir.

## 10. Güvenlik ve veri sınırı

- Transkript ve daily metni güvenilmeyen veri kabul edilir.
- Model komutları shell stringiyle değil argv listesiyle çalıştırılır.
- Flush modeline yazma aracı verilmez ve çıktı şeması doğrulanır.
- Compile staging ve allow-list doğrulaması olmadan vault'a yazamaz.
- Secret local settings/yedekleri gitignore ve staging kapılarıyla korunur.
- Upgrade secret geçmişini otomatik yeniden yazmaz; izlenen secret bulursa rotasyon uyarısı verir.
- Geçmiş import, arşivi okumadan ve daily yazmadan önce iki açık onay kapısı uygular.

Tarihsel bulgular `docs/GATE-REVIEW-SECURITY.md` içinde korunur; üst durum notu güncel çözümü ve
regresyon testlerini belirtir.

## 11. Test ve yayın kapısı

```bash
python3 scripts/render_integrations.py --check
python3 -m unittest discover -s tests -p '*_test.py'
bash tests/hooks_test.sh
bash tests/upgrade_settings_test.sh
bash tests/upgrade_transaction_test.sh
git diff --check
```

Windows job'ı ayrıca `tests/install_windows_test.ps1`, `tests/windows_native_test.py` ve gerçek
`runtime_platform` kilit testlerini `windows-latest` üzerinde çalıştırır.

Testler gerçek model/ağ çağrısı yapmaz. Provider stub'larıyla eşzamanlılık, hostile input,
allow-list, quota fallback, global kurucu idempotency'si, Windows yol köprüsü ve upgrade transaction
kapıları temp vault'larda doğrulanır.

## 12. Upstream politikası

Orijinal `avenoxai/avenoxbeyin` upstream kaynağıdır. `upstream_sync.sh check` farkları listeler;
`merge` temiz worktree ve geri dönüş dalı ister, commit etmeden birleştirmeyi bırakır. Upstream
değişikliği provider-neutral sözleşmeyi, staging güvenliğini veya kullanıcı hafızası kapılarını
atlayamaz.

## 13. İsim ve sürüm

- Proje: **Respected Brain**
- Vault adı: kullanıcı seçer; `respectedOS` zorunlu değildir.
- Companion adı: kullanıcı seçer; `Respected` zorunlu değildir.
- Çekirdek damgası: `.beyin-version = 2.0.0`
- Multi-AI damgası: `.beyin-multi-version = 1.3.0`
- Sabit iç hafıza yolu: `🔮 850-Companion/`

Orijinal proje ve Avenox atfı korunur; bağımsız projenin kurulum adresi
`https://github.com/respected0/respectedbrain` olur.
