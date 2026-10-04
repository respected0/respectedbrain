---
name: beyin-doktor
description: Beynin sağlık kontrolü; hook, hafıza ve vault hijyenini denetler. "beyin doktor", "sağlık kontrolü" için kullan.
---

# Beyin Doktoru

Bu skill beynin mekanik katmanını denetler: hook'lar tetikleniyor mu, script'ler çalışmış mı,
loglar tazeliğini koruyor mu, vault kirlenmiş mi. Amaç sessiz arızayı görünür yapmak.

## Nasıl çalışırsın

1. Global bağlantıdaki kayıtlı vault'u `respectedbrain vault list` ile doğrula. Örneklerdeki
   `UUID` yer tutucusunu seçilen gerçek kasa kimliğiyle değiştir; birden fazla kasa varsa
   kimliği netleştirmeden kontrolü başlatma.
2. Notların kökü VaultRoot'tur. DataRoot/config.json kullanıcı yapılandırmasıdır;
   DataRoot/vaults/<UUID>/state teknik durum, DataRoot/vaults/<UUID>/cache geçici veridir.
   RESPECTED_DATA_DIR override'ını önce kontrol et. Varsayılan DataRoot Windows Known Folder
   LocalAppData/RespectedBrain, Linux XDG_DATA_HOME/respectedbrain (yoksa ~/.local/share/respectedbrain),
   macOS ~/Library/Application Support/RespectedBrain'dir. AppRoot kurulu uygulamadır; buraya yazma.
3. Native launcher `respectedbrain` (Windows'ta `respectedbrain.exe`) kullanılır; kurulu motor
   ayrıca Python istemez. POSIX dosya kontrol örneklerini Windows'ta mevcut PowerShell/dosya
   okuma araçlarıyla aynı salt okunur ölçütlere göre uygula.
4. Her kontrolün çıktısını 🟢 / 🟡 / 🔴 sınıfla, kanıt yollarını tek tabloda göster.
5. Her kırmızı için düzeltme planı, en sonda tek cümlelik hüküm ver.

```text
respectedbrain vault list
respectedbrain configure
respectedbrain --version
```

Kontroller salt okunurdur. Repair, compile, maps, briefing ve hook yazabilir veya model
çağırabilir: aşağıdaki düzeltme örneklerini yalnız kullanıcı ilgili plan ID'sini seçince uygula.

Eksik bir tohum not için kaynak checkout gerekmez. Kurulu paket kaynak kökü Windows/Linux'ta
`AppRoot/app/respectedbrain/resources`, macOS'ta
`AppRoot/Contents/MacOS/app/respectedbrain/resources` olur. Kaynak kökünü salt okunur doğrula;
tohum mevcut değilse dosya içeriği uydurma, eksik dağıtımı raporla. Kopyalama yalnız seçilmiş
düzeltme ID'sinde, hedef hâlâ yoksa exclusive-create ile yapılır; kişisel içerik ezilmez.

## Kontroller

### 1. Native launcher ve hook kayıtları

Kullanılan provider'ın hook/notify kayıtlarını oku. Komut kurulu native launcher'a, doğru
provider/event çiftine ve seçilen --vault-id kimliğine gitmeli. Eksik native motor veya eski
betik bağlantısı kırmızıdır. Shell dosyalarını depodan kopyalama; onaylanan düzeltme:

```text
respectedbrain repair --vault-id UUID
```

### 2. Araç adaptörleri ve bağlantılar

Yalnız etkin integration bayrakları ve kullanılan provider için global talimat, MCP ve hook
kayıtlarını kontrol et. DataRoot/install-manifest.json ile gerçek içerik/hash farkını raporla.
Kapalı integration'ın yokluğu arıza değildir. Onaylanan düzeltme native repair'dir; kullanıcının
ilgisiz JSON/TOML anahtarlarını koru, hash çakışmasında üzerine yazma.

### 3. Özyineleme koruması

Hook komutunun native hook girişine bağlı olduğunu doğrula. İç model çağrılarında
BEYIN_INVOKED_BY koruması motor içinde uygulanır; shell dosyalarına elle guard ekleme.
Aynı olayı iki bağlantı tetikliyorsa ayrı bulgu yap. Eksik/eski bağlantıyı kullanıcı onayıyla
native repair üzerinden düzelt.

### 4. Native motor ve model CLI

Configure çıktısındaki preferences.summary_provider, provider_priority ve provider_fallback
alanlarını oku. İşletim sisteminin salt okunur executable keşfiyle claude, codex, agy, gemini
ve cursor-agent erişimini kontrol et. Native motor var ama seçili provider ve izinli fallback'ler
yoksa kırmızı. auto kaynak provider'ı önce dener, geçici kota/timeout/5xx hatalarında izinli
fallback'e geçebilir; BEYIN_LLM_COMMAND özel komutu olabilir. Onaylanan tercih değişikliği:

```text
respectedbrain configure --summary-provider auto
```

### 5. UUID ve teknik durum sınırı

DataRoot/config.json schema_version 3, vault UUID kaydı ve VaultRoot/.respected.json
kimliği tutarlı olmalı. UUID state/cache/overrides yolları VaultRoot ve AppRoot dışında olmalı.
Yeni kasada durum kaydı yoksa sarı; yanlış kimlik veya vault içine runtime yazımı kırmızı.
State/idempotency dosyalarını silerek düzeltme önerme; kimlik çakışmasını önce kanıtla.

### 6. Günlük log tazeliği

```bash
f=$(ls -t daily/*.md 2>/dev/null | head -1); if [ -z "$f" ]; then echo "daily: hic log yok"; else m=$(stat -f %m "$f" 2>/dev/null || stat -c %Y "$f"); n=$(date +%s); echo "daily: $f, $(( (n - m) / 3600 )) saat once yazildi"; fi
```

🟢 48 saatten yeni. 🟡 48 ile 96 saat arası. 🔴 96 saatten eski veya hiç log yok.
Düzeltme: oturum bitir ve yeniden başlat, sonra bu kontrolü tekrarla. Hâlâ boşsa 1, 2 ve 4
numaralı kontrollere dön, arıza flush zincirinde.

### 7. Derleme durumu

DataRoot/vaults/<UUID>/state/compile-state.json içindeki last_run, last_status ve ingested
sayısını oku. last_run 48 saatten yeni ve last_status ok ise yeşil; yeni kasada state yoksa
sarı; fail veya beklenmeyen eskilik kırmızı. Onaylanan teşhis ve gerçek derleme örnekleri:

```text
respectedbrain compile --vault-id UUID --dry-run
respectedbrain compile --vault-id UUID
```

Dry-run model çağırmaz ve günlük/bilgi notlarını değiştirmez; teknik kilit veya hata kaydı
oluşturabilir. İkinci komut model kotası tüketebilir; ikisini de uygulama onayı kapsamıyla çalıştır.

### 8. Sağlık kayıtlarındaki son hatalar

UUID state dizinindeki health.json ve health.warning.json dosyalarını oku; component,
provider, error ve zaman alanlarını raporla. Son 48 saatte hata kırmızı; eski çözülmüş kayıtları
bugünkü arızayla karıştırma. Flush hatasında transkript/model, compile hatasında model ve state
write zincirini kontrol et. Hata dosyasını silerek sistemi sağlıklı göstermeye çalışma.

### 9. Bilgi indeksi büyüklüğü

```bash
if [ -f knowledge/index.md ]; then echo "index: $(wc -l < knowledge/index.md | tr -d ' ') satir"; else echo "index: DOSYA YOK"; fi
```

Oturum başında indeksin sadece ilk 150 satırı bağlama giriyor.
🟢 150 satır ve altı. 🟡 151 ile 300 satır arası, alt sıralar artık enjekte edilmiyor.
🔴 300 satırın üstü: özet indeks zamanı.
Düzeltme: indeksi tema başlıklarına göre grupla, eski satırları tek bir özet satırında topla,
detay makalede kalsın. Dosya hiç yoksa paket kaynaklarındaki
`vault-template/knowledge/index.md` dosyasını seçilen düzeltme planına ekle.

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

### 12. Uygulama sürümü ve taşınabilir marker

Native --version çıktısını ve VaultRoot/.respected.json schema_version 3/UUID alanlarını
kontrol et. Marker uygulama sürümü değil kasa kimliğidir. Eski kasa için kullanıcı tarafından
seçilmiş kaynak ve yeni doğrulanmış dağıtımla native migrate önizlemesi öner; teşhiste uygulama.

### 13. Kurallar dosyası

```bash
if [ -f "🔮 850-Companion/Kurallar.md" ]; then echo "kurallar: var, $(wc -l < "🔮 850-Companion/Kurallar.md" | tr -d ' ') satir"; else echo "kurallar: YOK"; fi
```

🟢 var. 🟡 yok: kullanıcının düzeltmeleri kalıcı hale gelmiyor.
Düzeltme: paket kaynaklarındaki `vault-template/🔮 850-Companion/Kurallar.md` dosyasını
`🔮 850-Companion/` altına kopyalamayı seçilen düzeltme planına ekle.

### 14. Çift etkin kanca

Global/proje ve local provider kayıtlarını mevcut JSON/TOML okuma araçlarıyla karşılaştır.
Claude SessionStart/UserPromptSubmit/SessionEnd/PreCompact olaylarında native respectedbrain
hook komutu olay başına tam 1 olmalı: 0 eksik, 2+ çift tetikleme. Codex notify ve diğer
provider bağlantılarında da aynı olayın iki kez bağlı olup olmadığını kontrol et.
İlgisiz hook/env/permissions alanlarına dokunmadan düzeltme planla.

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

### 16. Wikilink, frontmatter ve tekrarlar

Bu native kontroller salt okunurdur:

```text
respectedbrain maintenance --vault-id UUID vault_linter --json
respectedbrain maintenance --vault-id UUID tiling_check --json
```

Kırık link/frontmatter hatası ve kritik mükerrer yoksa yeşil; yetim veya yüksek benzerlik sarı;
kırık hedef/bozuk metadata kırmızı. Kullanıcı onayına link/metadata düzeltme ve merge planı sun;
teşhiste --fix-dashes veya smart_merge çalıştırma.

### 17. Inbox ve otomatik haritalar

`📥 000-Inbox/Dump/` altındaki normal dosya sayısını ve en eski bekleme yaşını raporla.
`🎯 100-Command-Center/Vault-Map.md` ile `Skills-Map.md` yoksa veya vault yapısından eskiyse kırmızı
göster. Bu kontrolde dosya oluşturma ya da yenileme yapma.

### 18. Sabah brifingi ve zamanlayıcı

Yerel 08.00 sonrası bugünkü VaultRoot/🎯 100-Command-Center/Briefings/YYYY-MM-DD.md,
UUID state/briefing-health.json ve platformun Respected zamanlayıcısını salt okunur denetle.
Zamanlayıcı seçilen UUID'yi içermeli; schedule kapalıysa eksikliğini arıza sayma. Brifing yoksa
bunun zamanlayıcıdan mı model/compile hatasından mı kaynaklandığını kanıtla.

### 19. Graf topolojisi ve köprü analizi

16. kontroldeki native wikilink raporunu kullan; notların wikilink kenarlarını mevcut yerel
dosya araçlarıyla salt okunur incele. Kırık hedefleri, duplicate stem, yetim ve kopuk adaları
say; köprü görevi gören notları göster. Kritik yetim oranı <%5 ve kırık hedef yoksa yeşil,
kopuk adalar sarı, isim çakışması/graf bütünlüğü bozuksa kırmızı. Native CLI'de bağımsız
graph-analysis komutu yoktur; çalışmamış analizi çalıştı diye raporlama.

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
| Native hook kayıtları | 🟢 | launcher ve UUID seçimi doğru |
| settings.json bağlantısı | 🟢 | dört olay da bağlı |
| Özyineleme koruması | 🟢 | hepsinde var |
| Native motor ve model CLI | 🟢 | launcher var, agy ve codex kullanılabilir, provider auto |
| UUID teknik durum sınırı | 🟢 | schema 3, state/cache DataRoot içinde |
| Günlük log tazeliği | 🟡 | son log 51 saat önce |
| Derleme durumu | 🔴 | last_status fail:timeout |
| Sağlık kayıtları | 🔴 | dün compile hatası |
| Bilgi indeksi | 🟢 | 42 satır |
| iCloud çakışmaları | 🟢 | temiz |
| Git | 🟢 | repo var, 3 dosya kaydedilmemiş |
| Sürüm ve marker | 🟢 | native sürüm okundu, schema 3 UUID doğru |
| Kurallar | 🟢 | var, 24 satır |
| Çift etkin kanca | 🔴 | SessionEnd 2 kez bağlı |
| Sır yedeği artığı | 🟢 | temiz |
```

Tablodan sonra sadece 🔴 satırlar için "Düzeltme:" ile başlayan birer satır yaz, komutu da ver.
Sonra tek cümlelik hüküm: örneğin "Beyin ayakta ama derleyici iki gündür takılı, önce onu çöz."
Her şey yeşilse hüküm de kısa olsun: "Beyin sağlıklı, yapılacak bir şey yok."
