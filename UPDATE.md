# Respected Brain Güncelleme Kılavuzu (Update Guide)

Bu kılavuz, mevcut bir ikinci beyin kasanızı en güncel kararlı sürüme (`v0.0.1`) yükseltmek için 3 farklı yolu sunar.

> [!IMPORTANT]
> **Notlarınız Kutsaldır ve Kesinlikle Korunur:**
> Güncelleme işlemi yalnızca motor dosyalarını, hook adaptörlerini, ortak skill'leri ve şablonları yeniler.
> Kişisel kimlik dosyalarınıza (`🔮 850-Companion/Core.md`, `Journal.md`, `Threads.md`, `Last-Session.md`) ve aldığınız hiçbir kişisel nota asla dokunulmaz.
> Güncelleme öncesinde kasanızın bir yedeği sisteminizde (`~/.respected/update-backups/`) otomatik olarak saklanır.

---

## 3 Farklı Yoldan Güncelleme

### 1. Yol: AI-Native Güncelleme (En Kolay)
AI asistanınıza (Claude Code, Antigravity, Cursor veya Codex) doğrudan şu talimatı verin:

> *"Kasamı en son kararlı Respected Brain sürümüne güncelle."*

Asistanınız arka planda `update.py` veya `scripts/update_respected.py` üzerinden önizleme yapacak ve onayınızla kasanızı güvenle güncelleyecektir.

---

### 2. Yol: Tek Satır (One-Liner) Güncelleme

Repo klonlamanıza gerek kalmadan doğrudan terminalinizden güncelleyin:

#### Windows (PowerShell)
```powershell
irm https://raw.githubusercontent.com/respected0/secondbrain/main/update.ps1 | iex
```
*Özel kasa yolu belirtmek isterseniz:*
```powershell
& { irm https://raw.githubusercontent.com/respected0/secondbrain/main/update.ps1 } -VaultPath "$HOME\Documents\RespectedOS" -Apply
```

#### Linux & macOS (Bash)
```bash
curl -fsSL https://raw.githubusercontent.com/respected0/secondbrain/main/update.sh | bash
```
*Özel kasa yolu belirtmek isterseniz:*
```bash
curl -fsSL https://raw.githubusercontent.com/respected0/secondbrain/main/update.sh | bash -s -- --vault-path ~/Documents/RespectedOS --apply
```

---

### 3. Yol: CLI Terminal Sihirbazı (Geliştiriciler İçin)

Depo kök dizinindeyseniz etkileşimli güncelleme sihirbazını başlatın:

```bash
# Etkileşimli sihirbaz (kasa yolunu sorar ve önizleme gösterir):
python update.py

# Doğrudan uygulamak için:
python update.py --vault-path "/kasa/yolu" --apply
```

Windows'ta:
```powershell
py -3 update.py --platform windows-native
```

---

## Güncelleme Sonrası Sağlık Kontrolü

Güncelleme tamamlandıktan sonra kullandığınız AI asistanınızda şu komutu vererek kasayı doğrulayın:

> *"beyin doktor"*

Tüm kancaların, hafıza dosyalarının ve şablonların yeşil yandığını göreceksiniz.
