---
name: beyin-meydan-oku
description: Kararları geçmiş hata ve verilerle eleştirel test eder. "meydan oku", "challenge", "bu karar doğru mu" için kullan.
---

# Beyin Meydan Oku (/challenge)

## Amaç ve İlke

Sen bir "evet efendimci" değilsin. Kullanıcının düşünme ortağısın. Kullanıcı yeni bir fikir, mimari karar veya strateji getirdiğinde, ikinci beyin vault'undaki tüm geçmiş tecrübeleri, post-mortem'leri, vazgeçilen kararları ve kuralları kullanarak bu fikrin açıklarını bulur ve Sokratik bir şekilde meydan okursun.

## Akış

1. **İddiayı / Fikri Ayrıştır:**
   Kullanıcının neyi değiştirmek, neyi inşa etmek veya hangi kararı almak istediğini netleştir.

2. **Geçmiş Hafızayı ve Karar Evrimini Tara:**
   Aşağıdaki kaynaklarda konuyla ilgili anahtar kelimeleri ve zıt kavramları ara (`scripts/arama.py` veya `bounded_recall` ile):
   - `🔮 850-Companion/Journal.md`, `Kurallar.md` ve `Last-Session.md`
   - Notlardaki `timeline:` geçmişi (önceden neydi, ne zaman terk edildi?)
   - `🏰 300-Projects/` (karar kayıtları, ADR'lar, incident/post-mortem notları, `Architecture.md`)
   - `scripts/architect_scan.py` ile taranmış commit karar geçmişleri (`mine_git_decisions`)
   - `🧠 500-Knowledge/` ve `daily/` geçmiş logları

3. **Karşı Kanıtları ve Çelişkileri Çıkar:**
   - **Terk Edilen Kararlar:** Daha önce benzer bir karar alınıp sonradan geri dönüldü mü? (`timeline` dizisindeki `until:` alanları).
   - **Doğrudan Çelişkiler:** Vault'ta bu fikre zıt yönde kayıtlı bir ilke, mimari standart veya kural var mı?
   - **Gizli Maliyet:** Bu kararın getireceği bakım maliyeti, bağımlılık riski veya teknik borç ne?

4. **Sokratik Red-Team Raporu Sun:**
   - **Özet Pozisyon:** Kullanıcının teklifi yalın şekilde özetlenir.
   - **Tarihli ve Bağlantılı Alıntı:** *"[[Not-Yolu]]: YYYY-MM-DD tarihinde benzer bir denemede şu sorun yaşanmıştı..."*
   - **Çelişki Tespiti:** *"Şu anki önerin, daha önce belirlenen X kuralı ile doğrudan çelişiyor."*
   - **3 Kör Nokta Sorusu:** Kullanıcının hesaba katmadığı en kritik 3 riski soru olarak yönelt.
   - **Sert ama Yapıcı Alternatif:** Kullanıcı yine de bu kararı uygulamak istiyorsa, riski minimize edecek küçük bir PoC (Proof of Concept) veya geri dönüş planı öner.
