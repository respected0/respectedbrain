> Tarihsel kayıt (2026-10-03). Önceki düzenin tam metnidir; güncel kurulum talimatı değildir. [Güncel rehber](../../../../README.md), [sözleşme](../../../../docs/superpowers/specs/2026-10-03-modular-foundation-design.md).

# Respected Brain Güncelleme Kılavuzu (Update Guide)

Bu kılavuz, mevcut bir ikinci beyin kasanızı en güncel kararlı sürüme (`v0.0.1`) yükseltmek için 3 farklı yolu sunar.

> [!IMPORTANT]
> **Notlarınız Kutsaldır ve Kesinlikle Korunur:**
> Güncelleme işlemi yalnızca motor dosyalarını, hook adaptörlerini, ortak skill'leri ve şablonları yeniler.
> Kişisel kimlik dosyalarınıza (`🔮 850-Companion/Core.md`, `Journal.md`, `Threads.md`, `Last-Session.md`) ve aldığınız hiçbir kişisel nota asla dokunulmaz.
> Güncelleme öncesinde kasanızın bir yedeği sisteminizde (`~/.respected/update-backups/`) otomatik olarak saklanır.

---

## Farklı Yollardan Güncelleme

### 1. Yol: Windows Tek Tıkla Güncelleme (`setup.exe` — En Kolay)

Windows kullanıyorsanız doğrudan **`setup.exe`** dosyasını çalıştırın:
1. Kurulum programı mevcut kasanızı otomatik olarak tanır.
2. *"Yeni sürüme doğrudan HIZLI GÜNCELLEME yapmak istiyor musunuz?"* sorusuna **Evet** demeniz yeterlidir.
3. Kasanız saniyeler içinde güncellenir ve Kontrol Paneli açılır. Notlarınıza asla dokunulmaz.

---

### 2. Yol: AI-Native Güncelleme
AI asistanınıza (Claude Code, Antigravity, Cursor veya Codex) doğrudan şu talimatı verin:

> *"Kasamı en son kararlı Respected Brain sürümüne güncelle."*

Asistanınız arka planda `installer/update.py` veya `runtime/scripts/update_respected.py` üzerinden önizleme yapacak ve onayınızla kasanızı güvenle güncelleyecektir.

---

### 2. Yol: Evrensel Terminal Güncellemesi

Doğrudan terminalinizden tek komutla güncelleyin:

```bash
python setup.py --update
```

*Özel kasa yolu belirtmek isterseniz:*
```bash
python setup.py --update --vault-path ~/Documents/RespectedOS
```

---

### 3. Yol: CLI Terminal Sihirbazı (Geliştiriciler İçin)

Depo kök dizinindeyseniz etkileşimli güncelleme sihirbazını başlatın:

```bash
# Etkileşimli sihirbaz (kasa yolunu sorar ve önizleme gösterir):
python installer/update.py

# Doğrudan uygulamak için:
python installer/update.py --vault-path "/kasa/yolu" --apply
```

Windows'ta:
```powershell
py -3 installer/update.py --platform windows-native
```

---

## Güncelleme Sonrası Sağlık Kontrolü

Güncelleme tamamlandıktan sonra kullandığınız AI asistanınızda şu komutu vererek kasayı doğrulayın:

> *"beyin doktor"*

Tüm kancaların, hafıza dosyalarının ve şablonların yeşil yandığını göreceksiniz.
