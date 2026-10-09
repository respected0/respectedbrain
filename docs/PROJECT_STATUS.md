# 📍 Respected Brain — Proje Durumu

scope: project; confidence: verified; supersedes: ["Önceki tarihli uygulama planının aktif durum otoritesi"]

> Aktif durumun tek kaynağı bu belgedir. Tarihli test sonuçları [test matrisinde](TEST-MATRIX.md), ayrıntılı işlem kayıtları [kayıt indeksinde](records/README.md), güvenlik sınırları [SECURITY](SECURITY.md) içinde ve tarihli tam denetim [kayıt denetiminde](records/2026-10-installer-release/REPOSITORY_AUDIT.md) bulunur.

## 1. Kaynak ve yayın durumu — 2026-10-09

Modüler paket, kurulum seçimleri/hız düzeltmeleri ve kaynak temizliği ana checkout'a birleştirildi. Önceki çalışma dalı ve managed worktree kapatıldı; geliştirme kökü `Documents/ChatGPT/secondbrain` klasöründeki main'dir. Eski kaynak dönüşümünün ayrıntıları [uygulama kaydında](records/2026-10-modular-foundation/IMPLEMENTATION.md).

Son doğrulanmış ürün kodu `631c37eda13f569072e0436984cbf19f6b709ba8` için [37318525236 CI koşusu](https://github.com/respected0/respectedbrain/actions/runs/37318525236) 12/12 işi geçti. Kaynak main'e normal push ile gönderildi; tag veya herkese açık yeni release bu kapanışta oluşturulmadı. Daha sonraki belge düzenlemesini bu ürün kodunun native test sonucu gibi sunmayın.

2026-10-06 itibarıyla kaynak temizliği ve geçici Windows paket kontrolleri yürütüldü; ürünün tüm açık işleri tamamlanmadı. Python 3.13 teslim logunda 815 testin 800'ü geçti, 15'i platform koşulları nedeniyle atlandı. Python 3.12.14'teki dokuz Tcl hatası test sandbox'ının native dosya erişimiyle ayrıştırıldı: aynı interpreter/kod ile sandbox dışında 26 wizard testi geçti. Windows quoting, arama ve izole paket lifecycle kanıtlarının kapsamı [kaynak kabul kaydında](records/2026-10-source-cleanup/SOURCE_ACCEPTANCE.md) bulunur. Önceki CI sonucu bu yeni yerel değişikliklerin CI/native kabulü değildir. Dört hardening işi ve oturum açılmış sağlayıcı kabulü açık; genel tamamlanma onayı verilmedi.

2026-10-07 dördüncü güvenlik incelemesinin dört bulgusu kapatıldı: ardışık snapshot
zinciri, HTTP mutlak deadline, frozen GUI Tcl/Tk paketleme ve ölü snapshot kodu.
Odaklı düzeltme testleri `8/8`, gerçek Inno zinciri `1/1`, frozen GUI smoke
`exit 0`, package/source semantic compare `5/5` ve tam yerel Python suite son
düzeltme öncesi `875` test / `2` transient error / `16` skip koştu. Concurrency
düzeltmesi sonrası `50/50` stress ve `36/36` modül testi geçti. Bash hook testindeki
WSL `PYTHONPATH` kök nedeni düzeltildi ve `8/8` geçti. Ayrıntılı kanıt tablosu
[dördüncü inceleme düzeltme kaydında](records/2026-10-security-hardening/FOURTH_REVIEW_REMEDIATION.md)
içindedir.

2026-10-07 beşinci inceleme düzeltmesiyle kalan tek madde kapandı: Windows frozen paket güncel kaynakla yeniden üretildi. 84 ürün modülünün semantik karşılaştırması 84/84 eşit; gömülü `SessionBrain.load_index` artık `exclusive_lock` kullanıyor (gömülü ve kaynak opcode SHA256 `3d021bc4...`). Distribution integrity smoke `version/registry/maps/search/hook/MCP OK`, izole köklerle frozen GUI `exit 0` (1.234 s, stderr boş) verdi. Yeni EXE/Setup/manifest hash'leri [beşinci inceleme düzeltme kaydında](records/2026-10-security-hardening/FIFTH_REVIEW_REMEDIATION.md) işlendi. Tam suite kullanıcının hız tercihiyle yeniden koşulmadı; dış imza/provider kabulü açık.

2026-10-08/09 F7 takip düzeltmeleri Antigravity invocation/session ayrımını, failed retry sayacını ve model/günlük işaretçisi doğrulamasını kapsar. Ortak owner sınırı bütün tüketilen state/pending alanlarını ve günlük yazıldı iddiasının kalıcı marker karşılığını doğrular; yazıcı ve okuyucu aynı işlem nedenlerini kabul eder. F7 modülü 53 kalıcı testtir. İlk genel koşunun fixture/süre ölçümü hataları ve gece yarısı fixture saatleri düzeltildi. Son Python keşfinde 977 test / 961 PASS / 16 koşullu skip / 0 hata (280.218 s); dört uzun native vaka ayrıca PowerShell kurulum kapısında geçti. Böylece 981 vakalık keşfin kapsamı iki koşu üzerinden doğrulandı; ilk başarısız `run_all.py` logu yeşil diye sunulmaz. PowerShell launcher/zamanlayıcı ve Bash hooks/upstream kapıları geçti. Son EXE/Setup kaynakla 84/84 eşit; aynı artifact ile fiziksel Windows lifecycle 24/24 VERIFIED ve frozen GUI başlangıcı/profil atlaması exit 0. CI, gerçek attestation/Authenticode ve canlı provider/OS sandbox kabulü **NOT VERIFIED**. Tarihli RED/GREEN, kabul matrisi ve artifact kanıtı [F7 transcript düzeltme kaydında](records/2026-10-security-hardening/F7_TRANSCRIPT_REMEDIATION.md).

2026-10-07 paket-kaynak eşleşmesi tarihsel kanıttır; F7 ve uninstall takip düzeltmeleri 2026-10-08 yeniden üretilen pakete taşındı. Dış yayın kabulü açıktır.
2026-10-07 bağımsız teslim kontrolü de 84/84 eşitliği (exception table ve stack size dahil), gömülü kilidi ve üç paket hash'ini doğruladı. Yeni pakette distribution smoke ve izole GUI tekrar exit 0 verdi (GUI 1.000 s). Ayrıntı ve kanıt konumu [beşinci inceleme kaydında](records/2026-10-security-hardening/FIFTH_REVIEW_REMEDIATION.md). Yeni Setup.exe derlendi; önceki pakete ait Inno lifecycle sonucu bu yeni hash için tekrar koşulmuş kabul sayılmaz.
Gerçek GitHub Actions OIDC/Sigstore attestation/signature, Authenticode imzalı
outer installer, canlı provider oturumu ve canlı OS sandbox davranışı
**NOT VERIFIED**dır. Commit/push/tag yapılmadı; önceki CI bu teslimin doğrulaması
değildir.

Bu belgeler yeniden düzenlenirken canlı AppData programı ve sağlayıcı kurulum ayarları değiştirilmez. Kullanıcı kasasına program kurulumu, template taşıma veya not sıfırlama uygulanmaz; hafıza protokolünün devir ve belge bağlantısı düzeltmeleri ayrı not güncellemeleridir. Kaynak kodun modüler olması mevcut canlı kurulumun yeni yapıya geçirildiği anlamına gelmez.

## 2. Devreye alma ve rollout durumu

2026-10-08/09 [Windows yaşam döngüsü incelemesinde](records/2026-10-security-hardening/WINDOWS_LIFECYCLE_REVIEW.md) bulunan iki uninstall kaynak hatası düzeltildi: deferred CLI teknik temizleme tercihini korur; beş yerel AI hook dosyası uninstall sahipliğiyle kaydedilir ve update/repair boyunca kaybolmaz. Gerçek NativeBackend geçici köklerinde purge/keep-data temizliği, değiştirilmiş hook conflict'i, insan notu hash koruması ve rollback doğrulandı. Yeniden üretilen pakette 84/84 kaynak eşitliği ve 24/24 fiziksel Windows lifecycle kabulü var. Attestation bulunmayan yerel paket strict gerçek kurulum için hâlâ güvenli biçimde reddedilir; fixture doğrulaması bu yayın engelini kaldırmaz.

Ürün düzeyinde yeni kurulum (`setup`), güncelleme (`update`), onarım (`repair`), kaldırma (`uninstall`) ve eski kurulumları güvenle dönüştüren geçiş (`migrate`) motorları mevcuttur. Kaynak kaldırma bulguları ve paket/kaynak farkı kapatıldı; son native artifact'in genel ve dış kabul sınırları yukarıdadır. Migration özelliği mevcut kasayı koruma sözleşmesiyle üründe kalır.

Bu bilgisayara özel kişisel devreye alma tercihi Git dışındaki `.local/ROLLOUT.md` yerel kaydındadır; içeriği bu genel durum belgesinde tekrarlanmaz. Kaynak geliştirme çalışmaları canlı kurulum yapma veya mevcut kasayı değiştirme izni değildir. Canlı kurulum öncesinde program/veri kökleri ve sağlayıcı bağlantıları envanterlenmeli; bağımsız dış bağlantılar korunmalıdır.

## 3. Belge düzenleme kararı — 2026-10-05

Kullanıcı süreç aracına göre adlandırılmış repo/yerel klasörlerin kalmasını istemiyor. Onaylı kararlar `decisions/`, tamamlanan işlem ve kanıtlar tarihli `records/` altındadır. Yerel ikili test/yedek dosyaları hash doğrulamalı `.local/archives/` alanında korunur. [İşlem kaydı](records/2026-10-documentation/REORGANIZATION.md) yapılan düzenlemeleri ve doğrulama kapsamını açıklar.

Eski README'nin Türkçe anlatımı, tabloları ve SSS tarzı yeni giriş ve rehberlerde örnek alınır; eski “sıfır maliyet”, tüm sağlayıcılarda aynı sandbox veya doğrulanmamış platform iddiaları güncel bilgi diye taşınmaz. Eksiksiz dosya atlası ve JSON kaynağı korunur.

## 4. Kalan işler

| İş | Durum / Sınır |
| --- | --- |
| DNS transport, provider containment, snapshot, secret tarama, provenance consumer | Önceki dört güvenlik bulgusu ve SessionBrain kilidi 2026-10-07 artifact'inde doğrulandı. Yeni Windows teslimindeki açık maddeler aşağıdaki satırdadır; [karar](decisions/SECURITY_HARDENING.md) genel kabul değildir. |
| Dış kimlik ve yayın kanıtları | NOT VERIFIED: Authenticode sertifikası, gerçek GitHub Actions/Sigstore attestation ve tag yayını (commit/push yapılmadı) |
| Windows yaşam döngüsü teslimi | Kaynak uninstall bulguları ve paket/kaynak farkı kapandı. OPEN: gerçek yayın attestation eksikliği; [takip kanıtı](records/2026-10-security-hardening/F7_TRANSCRIPT_REMEDIATION.md). |
| Native OS round-trip ve GUI | Windows geçici köklerde lifecycle 24/24; PowerShell kurulum/launcher/zamanlayıcı geçti. Son frozen GUI başlangıcı ve tamamlanmış profil atlaması geçti; GUI alan doldurma/kaydetme etkileşimi ve diğer fiziksel OS hostları NOT VERIFIED. |
| Giriş yapılmış sağlayıcıların tam dış kabulü | NOT VERIFIED: canlı token/oturum ve sağlayıcı OS sandbox davranışı dış önkoşuldur |
| Yeni native paket ve canlı devreye alma | Kullanıcının son aşaması; geçici kabul, somut backup ve canlı rollout ile |

## 5. CI ve çalışma kuralları

Çalışma disiplini [AGENTS.md](../AGENTS.md) içinde tanımlıdır: Push sonrasında CI sürekli sorgulanarak beklenmez; bekleme ajanı/otomasyonu başlatılmaz. Sonuç çıkınca kullanıcı yeniden çağırır, o çağrıda gerçek sonuç incelenir. Kullanıcı istemedikçe paralel ajan çalıştırılmaz. Çalışma kayıtlarındaki eski yöntem talimatları bu tercihin üzerine yazamaz.

Aktif durum değişirse bu belge güncellenir; geçmiş sonuçlar tarihli kayıtlarda korunur. Diğer not ve rehberler yeni durum kopyası yazmak yerine buraya bağlanır.
