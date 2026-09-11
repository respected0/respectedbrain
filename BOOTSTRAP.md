# 🤖 Respected Brain: AI-Native Kurulum Protokolü (BOOTSTRAP.md)

Bu kılavuz, bir yapay zeka ajanının (**Claude Code, Cursor Agent, OpenAI Codex, Google Antigravity**) kullanıcı için sıfırdan bir **Respected Brain** kasası kurmasını sağlayan yetkili protokoldür.

> **Ajan Talimatı:** Kullanıcı *"Bu repoyu oku ve kasamı kur"*, *"Bana bir Respected Brain vault'u kur"* veya benzeri bir talimat verdiğinde, aşağıdaki adımları sırayla ve güvenle yürüt.

---

## 1. Ön Kontrol (Preflight)
Aşağıdaki gereksinimlerin sistemde mevcut olduğunu doğrula:
1. **Python:** Python 3.10 veya üzeri kurulu olmalıdır.
   - Windows: `python --version` veya `py -3 --version`
   - Linux / macOS / WSL: `python3 --version`
2. **Git:** `git --version`
3. **Mevcut AI Sağlayıcıları:** Sistemde hangi CLI araçlarının kurulu olduğunu tara:
   - Google Antigravity: `agy --version`
   - OpenAI Codex: `codex --version`
   - Anthropic Claude: `claude --version`
   - Cursor: `cursor-agent --version`

---

## 2. Kullanıcı Parametrelerini Belirleme
Kullanıcı aksini belirtmediyse aşağıdaki akıllı varsayılanları kullan; özel tercihi varsa kullanıcıya sor:

| Parametre | Varsayılan Değer | Açıklama |
| :--- | :--- | :--- |
| **VAULT_PATH** | Windows: `C:\Users\<Kullanıcı>\Documents\RespectedOS`<br>Linux/macOS: `~/Documents/RespectedOS` | Kasanın kurulacağı hedef klasör (boş olmalıdır). |
| **USER_NAME** | İşletim sistemi kullanıcı adı (`$USER` veya `%USERNAME%`) | Kullanıcının adı / hitap biçimi. |
| **USER_BIO** | `Geliştirici & Araştırmacı` | Kullanıcının çalışma alanı ve ilgi alanları. |
| **COMPANION** | `Jarvis` | Düşünme ortağı / hafıza asistanının adı. |
| **OS_NAME** | `RespectedOS` | Kasa ve işletim sistemi kimliği. |
| **SUMMARY_PROVIDER** | `auto` | Arka plan özetleyici (`auto`, `antigravity`, `codex`, `claude`, `cursor`). |
| **PROVIDER_PRIORITY** | `["antigravity", "codex", "claude", "cursor"]` (İsteğe bağlı) | Fallback sırasında taranacak sıra. |
| **ENVIRONMENT** | `native` | Çalışma ortamı (`native`, `wsl`, `hybrid`). |
| **DESKTOP_SHORTCUT** | `True` | Masaüstüne tek tıkla Obsidian açılış kısayolu ekleme. |
| **MORNING_BRIEFING** | `True` | Her sabah 08:00 otomatik brifing zamanlayıcısı kurma. |

---

## 3. Kurulum İcrası (Adım Adım)

Ajan olarak şu adımları terminal araçlarınla uygula:

### Adım 3.1: Şablonu Kopyalama
Hedef dizini oluştur ve `template/` klasörünün içeriğini hedef dizine eksiksiz kopyala:
```bash
# Örnek (Python üzerinden güvenli kopyalama):
python -c "import shutil, pathlib; shutil.copytree('template', '<VAULT_PATH>', dirs_exist_ok=False)"
```

### Adım 3.2: Yardımcı Betikleri Kopyalama
Repodaki `scripts/` klasörünün içeriğini `<VAULT_PATH>/scripts/` altına kopyala (kurulum ve senkronizasyon betikleri hariç: `install-windows.ps1`, `upstream_sync.sh` kopyalanmaz).

### Adım 3.3: Yer Tutucuları (Placeholders) Çözme
Kasadaki tüm dosyalarda geçen şu etiketleri kullanıcının değerleriyle değiştir:
- `{{OS_NAME}}` -> `$OS_NAME`
- `{{USER_NAME}}` -> `$USER_NAME`
- `{{USER_BIO}}` -> `$USER_BIO`
- `{{COMPANION}}` -> `$COMPANION`
- `{{VAULT_PATH}}` -> Hedef kasanın tam mutlak yolu
- `{{TODAY}}` -> Bugünün tarihi (`YYYY-MM-DD`)

### Adım 3.4: Yapılandırmayı Yazma
`<VAULT_PATH>/.beyin/config.json` dosyasını oluştur veya güncelle:
```json
{
  "summary_provider": "auto",
  "platform": "windows-native", // veya "portable" (Linux/macOS için)
  "python_command": ["python"],
  "provider_priority": ["antigravity", "codex", "claude", "cursor"]
}
```

### Adım 3.5: Entegrasyonları Derleme
Kasa içindeki platform entegrasyonlarını derle:
```bash
python scripts/render_integrations.py --root "<VAULT_PATH>" --platform <windows-native | portable>
python scripts/render_integrations.py --root "<VAULT_PATH>" --check
```

### Adım 3.6: İsteğe Bağlı Global Bağlantı
Kullanıcı global kurallara ve yeteneklere bağlanmak istiyorsa:
- Antigravity / Gemini için: `python scripts/install_antigravity_global.py`
- Claude / Codex / Cursor için: `python scripts/install_global.py`

### Adım 3.7: Masaüstü Kısayolu Oluşturma (İsteğe Bağlı)
Kullanıcı onay verdiyse:
- Windows: Masaüstüne `<OS_NAME>.url` dosyası oluştur:
  ```ini
  [{000214A0-0000-0000-C000-000000000046}]
  Prop3=19,0
  [InternetShortcut]
  IDList=
  URL=obsidian://open?vault=<OS_NAME>
  ```
- Linux / WSL: `~/Desktop/<OS_NAME>.desktop` oluştur (`chmod +x` ile).

### Adım 3.8: Sabah Brifingi Zamanlayıcısı (İsteğe Bağlı)
Kullanıcı sabah 08:00 otomatik brifingini istiyorsa:
```bash
python scripts/install_briefing_schedule.py "<VAULT_PATH>" --home "<KULLANICI_HOME>" --platform <windows-native | windows-wsl | linux | macos> --apply
```

---

## 4. Doğrulama ve Tamamlama Raporu
Kurulum tamamlandığında ajanın kullanıcıya şu özeti sunması gerekir:
1. Kasanın kurulduğu tam yol.
2. Tanımlanan kullanıcı ve Companion adı.
3. Seçilen birincil model ve fallback sırası.
4. Kasanın **Obsidian** ile nasıl açılacağı:
   - *"Obsidian'ı aç -> 'Open folder as vault' seçeneğine tıkla -> `<VAULT_PATH>` klasörünü seç."*
5. Masaüstü kısayolu oluşturulduysa konumu (`obsidian://open?vault=<OS_NAME>`).
6. Sabah brifingi zamanlayıcısının durumu (Aktif: 08:00 veya Pasif).
