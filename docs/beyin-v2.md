# Respot Brain: Kendi Kendine Hatırlayan Çoklu-AI İkinci Beyin

Bu belge bağımsız kurulum kılavuzudur. Güncel kaynak:
`https://github.com/respected0/respot-brain`.

Respot Brain bir model veya sohbet uygulaması değildir. Obsidian Markdown vault'unu Antigravity,
Codex, Cursor ve Claude Code arasında ortak hafıza yapan yerel bir katmandır. Bir agentla alınan
kararlar kapanışta günlük özete dönüşür; sonraki agent aynı vault'tan iş bağlamını alır.

## Ne taşınır, ne taşınmaz?

Taşınır:

- son oturum ve açık konular
- kullanıcının kalıcı kuralları
- günlük oturum özetleri
- derlenmiş kavramlar, bağlantılar ve bilgi indeksi
- aynı kanonik skill ve çalışma talimatları

Taşınmaz:

- Antigravity/Codex/Cursor/Claude arayüzünün ham chat geçmişi
- henüz kapanmamış ve flush edilmemiş son mesajlar
- giriş yapılmamış bir sağlayıcının kotası veya hesabı

## En hızlı kurulum

```bash
git clone https://github.com/respected0/respot-brain.git
cd respot-brain
```

Klasörü tercih ettiğin coding agentta aç ve şunu yaz:

```text
SETUP.md dosyasını tamamen oku ve ikinci beynimi kurmak için adımları uygula.
Vault adını ve yolunu bana sor. Kullandığım agentları global bağla. Özetleyici tercihini auto bırak.
```

Kurulumu Claude yapmak zorunda değildir. Antigravity, Codex, Cursor veya Claude Code aynı runbook'u
uygulayabilir.

## Kurulum görüşmesinde ne sorulur?

Agent şu kararları kullanıcıdan alır:

1. Kullanıcının adı ve kısa bağlamı
2. AI ortağının adı
3. Vault klasörünün adı ve mutlak yolu
4. İsteğe bağlı proje/alan klasörleri
5. Opsiyonel mem0 tercihi
6. Kullanılan agentlar: Antigravity, Codex, Cursor, Claude
7. Her kod reposundan merkezi vault'a global bağlantı isteği

Vault adı serbesttir. `respectedOS` yalnız kişisel bir örnektir. Companion adı da serbesttir;
`Respot` zorunlu değildir. İçteki `🔮 850-Companion/` klasörü runtime sözleşmesi nedeniyle sabittir.

## Taze kurulum mu, yükseltme mi?

`SETUP.md` önce aday vault'ları tarar:

- Beyin yoksa template'ten taze vault oluşturur.
- `CLAUDE.md` ve `🔮 850-Companion/` bulunan, `.beyin-version` bulunmayan vault'u v1 sayar.
- v1 bulunduğunda `scripts/upgrade.sh` ile doğrulanmış snapshot → apply → finalize zincirini uygular.
- Zaten v2 olan vault'a `enable_multiai.py` ile eksik adapter/runtime parçalarını ekleyebilir.

Yükseltme mevcut companion hafızasını, Dashboard'u ve kullanıcı notlarını değiştirmez.
`.beyin-version` bütün kapılar geçtikten sonra en son yazılır.

## Elle global bağlantı

Global bağlantı, vault açık değilken normal bir kod reposunda çalışan agentın da aynı hafızayı
bulmasını sağlar. Komutlar önce preview üretir.

Windows + WSL:

```bash
python3 scripts/install_global.py "/mnt/c/Users/KULLANICI/Documents/BenimBeynim" \
  --home "/mnt/c/Users/KULLANICI" --platform windows-wsl --providers all

# Liste doğruysa aynı komuta ekle:
# --apply
```

macOS/Linux:

```bash
python3 scripts/install_global.py "/mutlak/yol/BenimBeynim" \
  --home "$HOME" --platform portable --providers all
```

`all` yerine `antigravity,codex` gibi bir alt küme verilebilir. Kurucu mevcut kullanıcı kurallarını
ve hook'larını silmez; yalnız işaretli Respot bloğunu birleştirir, skill'leri kurar ve yedek alır.

## Günlük kullanım

1. Herhangi bir kod reposunu ana agentında aç.
2. Normal çalış; önemli kararları özellikle söylemek faydalıdır ama dosya yönetmek zorunda değilsin.
3. Agent oturumunu normal biçimde kapat.
4. Birkaç saniye içinde `daily/YYYY-MM-DD.md` güncellenir.
5. Başka agentı aç; son oturum ve bilgi indeksi ortak bağlama girer.

Kritik geçişte ilk agentı kapatmadan diğerine geçersen son mesajların özeti henüz oluşmamış olabilir.

## Özetleyici ve kota davranışı

Varsayılan ayar:

```json
{
  "summary_provider": "auto"
}
```

`auto`, oturumu kapatan agentın CLI'ını önce dener. Örneğin Codex oturumu Codex ile özetlenir.
CLI kurulu değilse veya kota/rate-limit/timeout/geçici servis hatası verirse kurulu ve giriş yapılmış
diğer CLI denenir.

Desteklenen arka plan komutları:

| Provider | Komut |
| --- | --- |
| Antigravity | `agy` |
| Codex | `codex exec` |
| Cursor | `cursor-agent -p` |
| Claude | `claude -p` |

Kalıcı ilk tercih yalnız kullanıcı isterse seçilir:

```bash
python3 scripts/set_summary_provider.py auto
python3 scripts/set_summary_provider.py antigravity
python3 scripts/set_summary_provider.py codex
python3 scripts/set_summary_provider.py cursor
python3 scripts/set_summary_provider.py claude
```

Bu komut coding agentı sabitlemez. Belirli provider seçilmiş olsa bile geçici kota/servis hatasında
fallback devam eder. Kimlik doğrulama veya kalıcı yapılandırma hatası gizlenmez; düzeltilmesi için
raporlanır.

## “Gece derleme” ne yapar?

Saat 18:00'de bir program ChatGPT veya IDE açmaz. Her başarılı kapanıştan sonra günlük özet oluşur.
Yerel saat 18:00'den sonraysa, değişmiş ve derlenmemiş daily girdileri bulunduğunda aynı headless
CLI hattı bilgi derlemesini başlatır. O gün 18:00'den sonra hiç oturum kapanmazsa bir sonraki uygun
kapanışta çalışır.

Derlenmiş içerik:

```text
knowledge/
├── index.md
├── log.md
├── concepts/*.md
└── connections/*.md
```

Derleme staging klasöründe yapılır ve yalnız bu allow-list içindeki dosyalar doğrulanarak vault'a
taşınır.

## Ortak rules ve skill'ler

Tek kaynaklar:

- `.beyin/instructions.md`
- `.beyin/skills/*/SKILL.md`

Üretilen adapterlar:

- Codex: `AGENTS.md`, `.codex/hooks.json`, `.agents/skills/`
- Cursor: `.cursor/rules/beyin.mdc`, `.cursor/hooks.json`, `.agents/skills/`
- Antigravity: `.agents/rules/beyin.md`, `.agents/hooks.json`, `.agents/skills/`
- Claude: `CLAUDE.md`, `.claude/settings.json`, `.claude/skills/`

Değişiklikten sonra:

```bash
python3 scripts/render_integrations.py
python3 scripts/render_integrations.py --check
```

## Windows + WSL

Windows IDE'leri hook komutunda `wsl.exe --cd <vault>` kullanır. Hafıza motoru WSL'deki Python ve
Bash ile çalışır; Obsidian aynı klasörü `C:\...` yolundan açar. Vault'un `/mnt/c/...` gibi Windows
diskinin WSL görünümünde olması gerekir.

Bir defalık yapılabilecekler:

- AI CLI'larına kendi hesaplarıyla giriş yapmak
- Codex yeni hook'u ilk gördüğünde `/hooks` ekranından güven vermek
- Global ayar eklendikten sonra IDE'yi yeniden başlatmak

## macOS ve Linux

macOS, orijinal avenoxbeyin akışının test edildiği platformdur. Bash/Python motoru korunur ve
isteğe bağlı Obsidian `.app` başlatıcısı üretilebilir. Linux runtime taşınabilir yazılmıştır;
`.desktop` başlatıcısı vardır ancak gerçek Linux masaüstü saha testi tamamlanmamıştır.

## Sağlık kontrolü

Kullandığın agenta `beyin doktor` yaz. Skill şu alanları salt okunur denetler:

- agent adapterları ve hook bağlantıları
- ortak runtime hook'ları ve recursion guard
- Python ve kurulu AI CLI'ları
- aktif summary provider ayarı
- daily/compile tazeliği ve sağlık kayıtları
- bilgi indeksi boyutu
- git durumu, çift hook ve secret yedekleri

Doktor hiçbir şeyi kullanıcı onayı olmadan düzeltmez.

## Geçmiş içe aktarımı

`geçmiş import` skill'i ChatGPT, Claude ve Gemini dışa aktarımlarını aylık daily parçalarına
çevirebilir. Arşivi okumadan önce salt-okunur preview için, dosya yazmadan önce ikinci kez açık
onay ister. Hassas konuşmalar varsayılan olarak dahil olduğundan tarih ve anahtar kelime filtreleri
sunulur. Daily içeriği ancak derleme çalışınca seçilen yerel CLI modeline gönderilir.

## Upstream yenilikleri

Orijinal repo upstream olarak tutulabilir:

```bash
./scripts/upstream_sync.sh check
./scripts/upstream_sync.sh merge
```

`merge` temiz worktree ister, geri dönüş dalı oluşturur ve sonucu commit etmeden bırakır. Böylece
orijinal projedeki yenilikler multi-AI ve güvenlik farkları incelenerek alınır.

## Sorun giderme özeti

- Daily oluşmadıysa: oturum yeterince anlamlı mı, hook güveni var mı, Python ve bir CLI girişli mi?
- Seçili provider limiti bittiyse: başka girişli CLI varsa otomatik fallback; yoksa CLI kur/giriş yap.
- Yeni agent bağlamı almadıysa: global kurulum, IDE restart ve agent hook dosyasını kontrol et.
- Aynı özet iki kez yazılıyorsa: proje+global dedup ve eski `settings.local.json` hook'larını doktorla
  kontrol et.
- Compile çalışmadıysa: 18:00 sonrası uygun kapanış olup olmadığını ve `compile-state.json` durumunu
  incele.

## Doğrulama komutları

Kaynak repo için:

```bash
python3 scripts/render_integrations.py --check
python3 -m unittest -v tests/scripts_test.py tests/multiai_test.py
bash tests/hooks_test.sh
bash tests/upgrade_settings_test.sh
bash tests/upgrade_transaction_test.sh
git diff --check
```

Bu testler gerçek modele veya ağa çağrı yapmaz.

## Maliyet ve veri

Respot Brain ayrıca API anahtarı veya abonelik satmaz. Hangi yerel CLI özeti/derlemeyi yaparsa
kullanım o sağlayıcının hesabına ve kotasına yazılır. Vault, günlükler ve derlenmiş bilgi yerel
dosyalardır; özetlenecek metin seçilen model sağlayıcısına CLI üzerinden gider.

## Credits

Fork, Avenox'un `avenoxbeyin` v2 çalışmasını temel alır. Bilgi derleme mimarisi Andrej Karpathy'nin
LLM knowledge-base deseninden esinlenir:
https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f

MIT lisanslıdır. Ayrıntı için repo kökündeki `LICENSE` dosyasına bak.
