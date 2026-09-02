---
name: beyin-doktor
description: Beynin sağlık kontrolü. Hook'lar, script'ler, hafıza dosyaları, günlük loglar, derleme durumu ve vault hijyeni tek tabloda raporlanır. "beyin doktor", "doktor", "sağlık kontrolü", "beyin çalışıyor mu", "hafıza bozuk mu" dendiğinde veya bir hafıza mekanizmasının sessizce çalışmadığından şüphelenildiğinde kullan.
---

# Beyin Doktoru

Bu skill beynin mekanik katmanını denetler: hook'lar tetikleniyor mu, script'ler çalışmış mı,
loglar tazeliğini koruyor mu, vault kirlenmiş mi. Amaç sessiz arızayı görünür yapmak.

## Nasıl çalışırsın

1. Vault kökünde (`.beyin/`, `AGENTS.md` veya `CLAUDE.md` bulunan klasör) çalış. Tüm yollar
   göreceli, mutlak yol yazma.
2. Önce `.beyin/config.json` içindeki platformu belirle. POSIX/WSL profilinde aşağıdaki Bash
   örneklerini, `windows-native` profilinde aynı salt-okunur ölçütleri PowerShell ve `py.exe -3`
   ile uygula. Bash veya `python3` komut adını native Windows'ta zorunlu tutma.
3. Her kontrolün çıktısını 🟢 / 🟡 / 🔴 olarak sınıfla.
4. Sonucu tek bir tabloda ver, her 🔴 için bir düzeltme satırı yaz.
5. En sonda tek cümlelik hüküm ver.

Kontroller salt okunurdur. Hiçbir şeyi kendiliğinden düzeltme, önce raporla, sonra kullanıcı
isterse düzelt.

## Kontroller

### 1. Hook dosyaları var mı ve çalıştırılabilir mi

```bash
for h in session-start prompt-counter session-end pre-compact; do f=".claude/hooks/$h.sh"; if [ ! -f "$f" ]; then echo "$h: DOSYA YOK"; elif [ ! -x "$f" ]; then echo "$h: calistirilabilir degil"; else echo "$h: ok"; fi; done
```

🟢 dördü de `ok`. 🔴 eksik veya çalıştırılabilir değil.
Düzeltme: `chmod +x .claude/hooks/*.sh`, dosya yoksa depodan kopyala.

### 2. Araç adaptörleri ve hook bağlantıları var mı

```bash
for f in AGENTS.md CLAUDE.md .codex/hooks.json .cursor/hooks.json .agents/hooks.json .agents/rules/beyin.md; do if [ -f "$f" ]; then echo "$f: var"; else echo "$f: YOK"; fi; done; python3 scripts/render_integrations.py --check 2>/dev/null || echo "adaptör drift'i var (kaynak repo dışındaki vault'ta bu kontrol atlanabilir)"
```

🟢 kullanılan aracın talimat ve hook dosyası var. 🔴 kullanılan aracın dosyası eksik.
Düzeltme: kaynak repoda `python3 scripts/render_integrations.py`; kurulmuş vault'ta kaynak
repodan `python3 scripts/enable_multiai.py <vault> --apply` çalıştır.

### 3. Özyineleme koruması her hook'ta var mı

```bash
for f in .claude/hooks/*.sh; do if grep -q 'BEYIN_INVOKED_BY' "$f"; then echo "$(basename "$f"): guard var"; else echo "$(basename "$f"): GUARD YOK"; fi; done
```

🟢 hepsinde var. 🔴 eksik. Guard'ı olmayan hook, arka plan `claude -p` çağrısında tekrar
tetiklenir ve sonsuz döngü riski doğar.
Düzeltme: dosyanın shebang'inden hemen sonraki satıra `[ -n "${BEYIN_INVOKED_BY:-}" ] && exit 0` ekle.

### 4. python3 ve en az bir model CLI yolda mı

```bash
if command -v python3 >/dev/null 2>&1; then echo "python3: $(python3 -V 2>&1)"; else echo "python3: YOK"; fi; n=0; for c in claude codex agy cursor-agent; do if command -v "$c" >/dev/null 2>&1; then echo "$c: var"; n=$((n+1)); else echo "$c: yok"; fi; done; echo "model_cli_sayisi: $n"; if [ -f .beyin/config.json ]; then echo "provider_ayari: $(python3 -c 'import json; print(json.load(open(".beyin/config.json")).get("summary_provider", "auto"))' 2>/dev/null || echo bozuk)"; else echo "provider_ayari: YOK"; fi
```

🟢 python3 ve en az bir model CLI var. 🔴 python3 yoksa flush ve derleme çalışmaz; model CLI
yoksa arka plan özetleyici durur. `auto`, oturumu gönderen agentın CLI'ını önce dener; geçici
kota/timeout/5xx hatalarında kurulu diğer CLI'lara geçer. Özel komut için `BEYIN_LLM_COMMAND`
kullanılabilir.

### 5. python3-missing işareti

```bash
if [ -f .claude/scripts/.state/python3-missing ]; then echo "isaret VAR, tarih: $(head -1 .claude/scripts/.state/python3-missing 2>/dev/null)"; else echo "isaret yok"; fi
```

🟢 işaret yok. 🔴 işaret var: hook'lar python3 bulamadığı için JSON kaçışını yapamamış.
Düzeltme: python3'ü kur, sonra dosyayı sil: `rm .claude/scripts/.state/python3-missing`.

### 6. Günlük log tazeliği

```bash
f=$(ls -t daily/*.md 2>/dev/null | head -1); if [ -z "$f" ]; then echo "daily: hic log yok"; else m=$(stat -f %m "$f" 2>/dev/null || stat -c %Y "$f"); n=$(date +%s); echo "daily: $f, $(( (n - m) / 3600 )) saat once yazildi"; fi
```

🟢 48 saatten yeni. 🟡 48 ile 96 saat arası. 🔴 96 saatten eski veya hiç log yok.
Düzeltme: oturum bitir ve yeniden başlat, sonra bu kontrolü tekrarla. Hâlâ boşsa 1, 2 ve 4
numaralı kontrollere dön, arıza flush zincirinde.

### 7. Derleme durumu

```bash
f=".claude/scripts/.state/compile-state.json"; if [ -f "$f" ]; then m=$(stat -f %m "$f" 2>/dev/null || stat -c %Y "$f"); n=$(date +%s); echo "state: $(( (n - m) / 3600 )) saat once guncellendi"; python3 -c "import json;d=json.load(open('.claude/scripts/.state/compile-state.json'));print('last_run:',d.get('last_run','yok'));print('last_status:',d.get('last_status','yok'));print('ingested:',len(d.get('ingested',{})),'log')" 2>/dev/null || echo "state dosyasi bozuk, JSON okunamadi"; else echo "compile: state dosyasi yok, henuz hic derleme calismadi"; fi
```

🟢 `last_run` 48 saatten yeni ve `last_status` `ok`. 🟡 state yok ama vault yeni kurulmuş veya
henüz akşam 18:00 olmamış. 🔴 `last_status` `fail:` ile başlıyor veya 48 saatten eski.
Düzeltme: elle bir tur çalıştır ve hatayı gör: `python3 .claude/scripts/compile.py --dry-run`,
sonra `python3 .claude/scripts/compile.py`.

### 8. Sağlık kayıtlarındaki son hatalar

```bash
if [ -f .claude/scripts/.state/health.json ]; then tail -c 2000 .claude/scripts/.state/health.json; else echo "health: kayit yok"; fi
```

🟢 kayıt yok veya son kayıt 7 günden eski. 🔴 son 48 saatte hata kaydı var.
Düzeltme: `component` alanına bak. `flush` ise transkript veya claude CLI, `compile` ise model
çağrısı sorunlu. Hata içindeki provider adına bak; hatayı okuduktan sonra dosyayı silebilirsin,
script yeniden yazar.

### 9. Bilgi indeksi büyüklüğü

```bash
if [ -f knowledge/index.md ]; then echo "index: $(wc -l < knowledge/index.md | tr -d ' ') satir"; else echo "index: DOSYA YOK"; fi
```

Oturum başında indeksin sadece ilk 150 satırı bağlama giriyor.
🟢 150 satır ve altı. 🟡 151 ile 300 satır arası, alt sıralar artık enjekte edilmiyor.
🔴 300 satırın üstü: özet indeks zamanı.
Düzeltme: indeksi tema başlıklarına göre grupla, eski satırları tek bir özet satırında topla,
detay makalede kalsın. Dosya hiç yoksa depodaki tohum dosyayı geri koy.

### 10. iCloud çakışma dosyaları

```bash
find . -name "* 2.*" -not -path "./.git/*" 2>/dev/null | head -20
```

🟢 çıktı boş. 🔴 çıktı var: iCloud aynı dosyanın iki kopyasını tutmuş, hafıza dosyalarının
bir kısmı yanlış kopyada olabilir.
Düzeltme: listelenen her dosyayı aslıyla karşılaştır (`diff "dosya.md" "dosya 2.md"`), gerekli
içeriği asıl dosyaya taşı, sonra çakışma kopyasını sil. Kullanıcıya sormadan silme.

### 11. Git deposu ve kaydedilmemiş değişiklik

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then echo "git: var, kaydedilmemis: $(git status --porcelain | wc -l | tr -d ' ') dosya"; else echo "git: REPO YOK"; fi
```

🟢 repo var ve kaydedilmemiş dosya 50'nin altında. 🟡 50 üstü birikmiş. 🔴 repo yok, yani
hafızanın geri alınabilir bir geçmişi yok.
Düzeltme: repo yoksa `git init` ve ilk commit. Birikme varsa commit at.

### 12. Sürüm dosyası

```bash
if [ -f .beyin-version ]; then echo "surum: $(head -1 .beyin-version)"; else echo "surum: DOSYA YOK, v1 vault"; fi
```

🟢 `2.0.0`. 🟡 dosya yok: bu bir v1 vault, yükseltme yapılabilir.
Düzeltme: SETUP.md içindeki yükseltme yolunu (B modu) uygula. Yükseltme mevcut hafıza
dosyalarına dokunmaz, sadece eksik parçaları ekler.

### 13. Kurallar dosyası

```bash
if [ -f "🔮 850-Companion/Kurallar.md" ]; then echo "kurallar: var, $(wc -l < "🔮 850-Companion/Kurallar.md" | tr -d ' ') satir"; else echo "kurallar: YOK"; fi
```

🟢 var. 🟡 yok: kullanıcının düzeltmeleri kalıcı hale gelmiyor.
Düzeltme: depodaki tohum `Kurallar.md` dosyasını `🔮 850-Companion/` altına kopyala.

### 14. Çift etkin kanca (settings.json + settings.local.json)

```bash
python3 - <<'PYCHK'
import json, os
EV = ("SessionStart", "UserPromptSubmit", "SessionEnd", "PreCompact")
V1 = ("session-start.sh", "prompt-counter.sh", "session-end.sh", "pre-compact.sh")
n = {e: 0 for e in EV}
for f in (".claude/settings.json", ".claude/settings.local.json"):
    try:
        d = json.load(open(f, encoding="utf-8"))
    except FileNotFoundError:
        continue
    except ValueError:
        print("%s: BOZUK JSON" % f); raise SystemExit(0)
    if not isinstance(d, dict):
        print("%s: JSON nesnesi degil" % f); continue
    for ev, ms in (d.get("hooks") or {}).items():
        if ev not in EV: continue
        for m in (ms or []):
            for h in (m.get("hooks") or []):
                if any(b in (h.get("command") or "") for b in V1):
                    n[ev] += 1
for e in EV:
    print("%s: %d" % (e, n[e]))
PYCHK
```

🟢 dört olayın da sayısı tam olarak `1`. 🔴 herhangi biri `2` veya daha fazla: o olayda
kancalar her seferinde iki kez çalışıyor, yani her prompt iki kez sayılıyor ve her oturum
sonunda iki flush tetikleniyor. `0` ise o olay hiç bağlı değil.
Düzeltme: `.claude/settings.local.json` içindeki beyin kanca girdisini sil, ilgisiz
kancalara ve `env`, `permissions` gibi diğer anahtarlara dokunma. Tek bağlantı
`.claude/settings.json` içinde kalmalı.

### 15. Vault içinde sır taşıyabilecek yedek artığı

```bash
find . -path ./.git -prune -o -type f \( -name "*.yedek" -o -name "*.yedek-*" -o -name "settings.local.json.*" -o -name "*.bak" -o -name "*.orig" \) -print 2>/dev/null | head -10; echo "---"; git ls-files 2>/dev/null | grep -E 'settings\.local\.json|\.yedek|\.env$' || echo "izlenen sirli dosya yok"
```

🟢 iki bölüm de boş. 🔴 bir yedek dosyası çıkarsa: bu dosyalar `settings.local.json`
kopyası olabilir ve API anahtarı taşır; ikinci bölümde bir şey çıkarsa sır zaten git
tarafından izleniyor demektir.
Düzeltme: yedeği vault dışına taşı ve `chmod 600` ver; git izliyorsa
`git rm --cached <dosya>` ile izlemeden çıkar, `.gitignore` kuralını doğrula, ve
sızmış anahtarı sağlayıcıdan **iptal edip yenile**.

### 16. Bağlantı, tekrar ve bayatlık adayları

Salt okunur olarak Markdown wikilink/bağlantı hedeflerini doğrula; aynı SHA-256 içeriğe sahip
notları kesin tekrar, benzer başlık veya örtüşen özet taşıyanları inceleme adayı olarak raporla.
Frontmatter `modified` alanı veya dosya mtime değeri 180 günden eski olan notları yalnız “bayatlık
adayı” say; otomatik olarak yanlış veya silinebilir kabul etme.

### 17. Inbox ve otomatik haritalar

`📥 000-Inbox/Dump/` altındaki normal dosya sayısını ve en eski bekleme yaşını raporla.
`🎯 100-Command-Center/Vault-Map.md` ile `Skills-Map.md` yoksa veya vault yapısından eskiyse kırmızı
göster. Bu kontrolde dosya oluşturma ya da yenileme yapma.

### 18. Sabah brifingi ve zamanlayıcı

Yerel saat 08.00'i geçtiyse bugünün `🎯 100-Command-Center/Briefings/YYYY-MM-DD.md` dosyasını,
`.claude/scripts/.state/briefing-health.json` kaydını ve platformun Respected zamanlayıcı tanımını
salt okunur denetle. Brifing yoksa bunun zamanlayıcı eksikliği mi model hatası mı olduğunu kanıtla.

## Düzeltme planı sözleşmesi

Teşhis tablosundan sonra her kırmızı ve anlamlı sarı bulgu için numaralı bir plan yaz:

`ID | Kanıt | Etkilenecek dosyalar | Önerilen işlem | Risk`

Bu skill planı **uygulamaz**. Kullanıcı bir veya daha fazla ID'yi açıkça seçmeden dosya yazma,
taşıma, silme, harita yenileme veya zamanlayıcı değiştirme. Seçim geldiğinde yalnız seçilen
maddeler yeni görev kapsamıdır; diğer bulgular salt okunur kalır.

## Rapor formatı

Tüm kontroller bittikten sonra tek tablo bas:

```
| Kontrol | Durum | Bulgu |
| --- | --- | --- |
| Hook dosyaları | 🟢 | dördü de yerinde ve çalıştırılabilir |
| settings.json bağlantısı | 🟢 | dört olay da bağlı |
| Özyineleme koruması | 🟢 | hepsinde var |
| python3 ve model CLI | 🟢 | python3 var, agy ve codex kullanılabilir, provider auto |
| python3-missing işareti | 🟢 | işaret yok |
| Günlük log tazeliği | 🟡 | son log 51 saat önce |
| Derleme durumu | 🔴 | last_status fail:timeout |
| Sağlık kayıtları | 🔴 | dün compile hatası |
| Bilgi indeksi | 🟢 | 42 satır |
| iCloud çakışmaları | 🟢 | temiz |
| Git | 🟢 | repo var, 3 dosya kaydedilmemiş |
| Sürüm | 🟢 | 2.0.0 |
| Kurallar | 🟢 | var, 24 satır |
| Çift etkin kanca | 🔴 | SessionEnd 2 kez bağlı |
| Sır yedeği artığı | 🟢 | temiz |
```

Tablodan sonra sadece 🔴 satırlar için "Düzeltme:" ile başlayan birer satır yaz, komutu da ver.
Sonra tek cümlelik hüküm: örneğin "Beyin ayakta ama derleyici iki gündür takılı, önce onu çöz."
Her şey yeşilse hüküm de kısa olsun: "Beyin sağlıklı, yapılacak bir şey yok."
