# Respected Brain Kaldırma Kılavuzu (Uninstall Guide)

Respected Brain sistem entegrasyonlarını (global AI kancaları, zamanlayıcılar, kısayollar, MCP sunucuları) temiz bir şekilde sisteminizden kaldırmak için bu rehberi kullanabilirsiniz.

> [!TIP]
> **Notlarınız Güvendedir:**
> Kaldırma aracı varsayılan olarak ikinci beyin kasanızı ve notlarınızı **kesinlikle silmez**. Sadece işletim sistemine ve AI araçlarına eklenen köprüleri ve görevleri kaldırır.

---

## Kaldırma Yolları

### 1. Yol: Windows `setup.exe` veya Denetim Masası (En Kolay)

Windows kullanıyorsanız komut satırına gerek kalmadan:
* **`setup.exe`** dosyasını çalıştırın -> **🗑️ Kaldır (Uninstall)** seçeneğini seçin.
* VEYA Windows **Ayarlar -> Uygulamalar -> Yüklü Uygulamalar -> Respected Brain -> Kaldır** butonuna tıklayın.

Tüm zamanlanmış sabah brifingi görevleri (`RespectedBrainBriefing`) ve kısayollar temizlenir. Notlarınız korunur.

---

### 2. Yol: Evrensel Terminalden Kaldırma

Terminalden doğrudan kaldırma aracını çalıştırın:

```bash
python setup.py --uninstall
```

VEYA interaktif olarak:
```bash
python setup.py
```
*(Menüden `[4] 🗑️ Kaldır` seçeneğini seçin).*

Windows'ta:
```powershell
py -3 uninstall.py
```

---

## Tam Temizlik (Kasa Dosyalarını da Silmek)

Eğer kasanızı, tüm notlarınızı ve şablonlarınızı da diskinizden tamamen silmek (purge) isterseniz:

```bash
python uninstall.py --purge-vault --vault-path "/kasa/yolu"
```

Windows PowerShell:
```powershell
py -3 uninstall.py --purge-vault --vault-path "$HOME\Documents\RespectedOS"
```

*Not: Normal kullanımda kasanın silinmesi için sizden açık metin onayı ("evet") istenir.*

### Otomasyon / Script Modu (Soru Sormadan Temizleme)
Test veya betik otomasyonlarında interaktif onay sorularını atlayıp doğrudan temizlemek için:
```powershell
py -3 uninstall.py --non-interactive --purge-vault
```
* **`--purge-vault`**: Kasa dizinini de tamamen siler (varsayılan davranış notları korumaktır).
* **`--non-interactive`**: "Emin misiniz?" ve onay sorularını sormadan işlemi doğrudan tamamlar.
