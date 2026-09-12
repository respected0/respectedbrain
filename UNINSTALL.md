# Respected Brain Kaldırma Kılavuzu (Uninstall Guide)

Respected Brain sistem entegrasyonlarını (global AI kancaları, zamanlayıcılar, kısayollar, MCP sunucuları) temiz bir şekilde sisteminizden kaldırmak için bu rehberi kullanabilirsiniz.

> [!TIP]
> **Notlarınız Güvendedir:**
> Kaldırma aracı varsayılan olarak ikinci beyin kasanızı ve notlarınızı **kesinlikle silmez**. Sadece işletim sistemine ve AI araçlarına eklenen köprüleri ve görevleri kaldırır.

---

## Kaldırma Yolları

### 1. Yol: Tek Satır (One-Liner) Kaldırma

Repo klonlamanıza gerek kalmadan sisteminizi temizleyin:

#### Windows (PowerShell)
```powershell
irm https://raw.githubusercontent.com/respected0/respectedbrain/main/uninstall.ps1 | iex
```

#### Linux & macOS (Bash)
```bash
curl -fsSL https://raw.githubusercontent.com/respected0/respectedbrain/main/uninstall.sh | bash
```

---

### 2. Yol: CLI Terminal Aracı

Depo dizinindeyseniz doğrudan çalıştırabilirsiniz:

```bash
python uninstall.py
```

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
