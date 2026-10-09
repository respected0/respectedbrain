# 📋 Dördüncü İnceleme Düzeltme Kaydı — 2026-10-07

scope: project; confidence: verified; supersedes: ["Dördüncü incelemede açık kalan ardışık snapshot, HTTP mutlak deadline, frozen GUI ve ölü snapshot kodu bulguları"]

## 1. Kapsam

Bu kayıt, dördüncü bağımsız incelemedeki dört bulgunun kapanışını ve elde edilen
yerel doğrulama zincirini tutar. Canlı program, canlı kullanıcı verisi, kişisel
RespectedOS kasası, canlı provider ayarları ve Git publication hedefi kullanılmadı.
Commit/push/tag/release/reset/stash/clean ve CI bekleme çalıştırılmadı.

## 2. Kapatılan bulgular

### A. Ardışık snapshot yayını

`maintenance/backup/publish_git_snapshot.py` artık yayımlanan snapshot zincirini
kullanıcının HEAD/index durumunu değiştirmeden receipt üzerinden izleyen
`remote_parent` ile kuruyor. İkinci ve üçüncü yayımlar, remote tarafında
fast-forward zincirini koruyacak şekilde aynı verified parent üzerinden ilerliyor.
`tests/security_hardening_fourth_fix_test.py` üç ardışık snapshot, süreç yeniden
başlaması, değişiklik olmayan not, kullanıcı HEAD ilerlemesi, dış remote değişimi
ve push başarısızlığından sonra tekrar davranışını sınıyor.

### B. HTTP mutlak deadline

`maintenance/ingestion/defuddle.py` içindeki `_DeadlineReader`, her bloklayan
okuma öncesi kalan mutlak süreyi sokete uyguluyor. Geç header byte sonrası idle
kalan bağlantı, eski socket timeout'unu beklemeden caller deadline'ında
sonlanıyor. Status, chunk-size ve trailer/body geç byte + durma senaryoları
aynı test dosyasında kalıcı hale getirildi.

### C. Frozen GUI Tcl/Tk paketleme

`tools/build_installer.py`, Python interpreter'ının `_tkinter.pyd`, Tcl ve Tk
runtime dizinlerini frozen pakete açıkça dahil ediyor.
`installation/wizard.py`, `TCL_LIBRARY` ve `TK_LIBRARY` değerlerini wizard
başlamadan önce forward-slash olarak ayarlıyor. Böylece sandbox dışında
gerçek frozen `setup --gui` yolu Tcl/Tk kaynaklarını buluyor ve pencere
oluşturuluyor.

### D. Ölü snapshot kodu

`publish_git_snapshot.py` içindeki eski, çağrılmayan snapshot implementation
blokunun tamamı kaldırıldı. Yeni helper davranışı ile karışan eski
index.stage/commit/push yolu artık dosyada yok.

### E. Tam suite’ta bulunan Bash test kök nedeni

Tam yerel zincir, Bash hook testinde WSL Python’ının `respectedbrain` paketini
bulamamasını gösterdi. `tests/hooks_test.sh` artık `PYTHONPATH` değerini kaynak
köküne açıkça bağlıyor; CI’deki editable install bağımlılığı kalkıyor.

### F. Session index concurrency

Tam suite ko?usu, `SessionBrain.load_index()`?in kilitsiz okuma yapmas? nedeniyle
Windows?ta atomic replace ile ?ak??t???n? g?sterdi. `load_index()` art?k `save_index()`
ile ayn? exclusive lock?u al?yor; e?zamanl? d?rt writer yar??? `50/50` tekrarla ve
ilgili mod?l `36/36` testle do?ruland?.

## 3. Kanıt zinciri

| Kanıt | Sonuç |
| --- | --- |
| `tests/security_hardening_fourth_fix_test.py` | VERIFIED: 8/8 test, 0 failure/error |
| Gerçek Inno install/update/uninstall zinciri | VERIFIED: 1/1 test, 133.566 s |
| Frozen GUI smoke | VERIFIED: `setup --gui`, exit 0, 1.815 s, izole app/data/vault |
| Frozen package/source semantic compare | VERIFIED: 5 kritik modül, 5/5 eşit |
| Distribution integrity smoke | VERIFIED: native frozen version/registry/maps/search/hook/MCP OK |
| Tam yerel Python suite (son concurrency d?zeltmesi ?ncesi) | 875 test, 2 transient error, 16 skip |
| Bash hook testi düzeltme sonrası | VERIFIED: 8/8 test, 0 failure/error |
| Windows native zincir | VERIFIED: platform smoke, PowerShell installer/launcher/scheduler paketleri geçti |

Güncel frozen paket hash’leri:

- `dist/RespectedBrain/respectedbrain.exe`:
  `D1773A844081BDDCC8F2074A184BD042B0E8E9804F7BBF749EEECDF514B1623E`
- `dist/RespectedBrain/distribution.json`:
  `6DC357B14002FDFC126F2D4AE04EB52975D2215FFCA1756624D49BF21266BE4E`

> Not: Bu hash'ler dördüncü tur paketine aittir; sonrasında SessionBrain concurrency düzeltmesiyle paket yeniden üretildi. Güncel hash'ler [beşinci inceleme düzeltmesinde](FIFTH_REVIEW_REMEDIATION.md) işlenmiştir.

## 4. Dış sınırlar

Gerçek GitHub Actions OIDC/Sigstore attestation/signature, Authenticode imzalı
outer installer ve GitHub tag yayını bu yerel teslimde üretilmedi. Canlı provider
oturumu ve canlı OS sandbox davranışı ayrı dış kabul konusudur. Bu kayıt dış
yayın veya canlı devreye alma izni değildir.
