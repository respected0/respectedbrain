# Respected Brain Feature Backlog

Bu dosya alınan ürün kararlarını ve yayın durumunu kaydeder. Aşağıdaki dört özellik `1.2.0`
sürümünde uygulanmıştır. Respected Brain tam yeniden adlandırma ve kayıpsız migration sınırı
`1.3.0` sürümüdür. Sonraki onaylı çalışmalar
[`UPSTREAM-ADOPTION-BACKLOG.md`](UPSTREAM-ADOPTION-BACKLOG.md) dosyasında tutulur.
Modern Codex transcript uyumluluğu ve Windows/WSL güvenilirlik düzeltmeleri `1.3.1` yama
sürümünde yayınlanmıştır; `1.4.0` özellik kapsamı ayrı kalır.

## Seçilen geliştirmeler

### 1. Beyin yol haritası

- İnsan tarafından yönetilen `Core.md`, kullanıcının kimliği ve çalışma biçimi için ana kaynak
  olarak kalır.
- Vault yapısını ve önemli giriş noktalarını anlatan bir Vault Map eklendi.
- Ortak kaynaktaki skill'leri ve ne zaman kullanılacaklarını anlatan bir Skills Map eklendi.
- Amaç, Claude, Codex, Antigravity ve Cursor arasında geçişte yeni agentın sistemi bütün vault'u
  taramadan anlayabilmesi.

### 2. Sabah brifingi

- Her gün saat 08.00 için planlanır.
- Bilgisayar 08.00'de kapalıysa Windows'un kaçırılan görevi ilk fırsatta çalıştırma davranışıyla
  bilgisayar açıldığında hazırlanacak.
- Aynı gün içinde yalnızca bir kez üretilecek ve gerçek hazırlanma saati notta görünecek.
- Dün tamamlananlar, açık işler, devam eden projeler, bugünün öncelikleri ve unutulmaması gereken
  konuları özetleyecek.
- Tek bir modele sabitlenmeyecek; mevcut provider seçimi ve fallback zincirini kullanacak.

### 3. Beyin temizliği

- Mevcut `beyin-doktor` salt okunur teşhis katmanı olarak kalacak.
- Bozuk bağlantılar, tekrarlar, bayat bilgiler, bekleyen notlar ve mekanik arızalar için düzeltme
  planı önerecek.
- Kullanıcı onayı olmadan dosya taşımayacak, silmeyecek veya düzeltmeyecek.

### 4. Inbox düzenleme

- `📥 000-Inbox/Dump/` içindeki ham notlar için hedef klasör, başlık, etiket ve bağlantı önerileri
  üretecek.
- Önce önizleme gösterecek; kullanıcı onayından sonra değişiklik uygulayacak.

## Bilinçli olarak kapsam dışı bırakılanlar

- Gizlilik kontrolü: mevcut kullanımda AI'ın okuyamayacağı bir vault alanı planlanmıyor.
- Haftalık değerlendirme: daily kayıtlar ve günlük görüşmeler şimdilik yeterli görülüyor.
- Güvenli paylaşım: şu an paylaşılacak bir bilgi akışı bulunmuyor.

## Durum

Üç dilimli mimari 2026-08-31'de onaylandı: güvenli compiler + haritalar, sabah brifingi + platform
zamanlayıcıları, ardından salt-okunur doktor planı + onay kapılı inbox düzenleme. Gizlilik kontrolü,
haftalık değerlendirme ve güvenli paylaşım kapsam dışı kalmaya devam ediyor.

Bu üç parçalı mimari `3ec18e6` commit'iyle `1.2.0` olarak tamamlandı. `1.3.0`, ürün ve teknik
namespace'i Respected Brain'e taşıyan uyumluluklu migration sürümüdür. `1.3.1` modern Codex
transcript uyumluluğu, `1.3.2` ise UAC, conhost headless ve cross-platform stabilizasyon yamasıdır.
Dokuz maddelik `1.4.0` kapsamı (model normalizasyonu, 1-shot retry, pycache temizliği,
immutable event log, Linux CI ve Restic/Git yedekleme) `1.4.0` sürümünde eksiksiz tamamlanmıştır.
