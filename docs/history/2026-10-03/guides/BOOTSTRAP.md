> Tarihsel kayıt (2026-10-03). Önceki düzenin tam metnidir; güncel kurulum talimatı değildir. [Güncel rehber](../../../../README.md), [sözleşme](../../../../docs/superpowers/specs/2026-10-03-modular-foundation-design.md).

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
Kuruluma başlamadan önce kullanıcıdan en az kasa yolu, kullanıcı adı, kasa adı, çalışma ortamı ve model fallback sırasını açıkça al. Diğer seçenekleri de göster; kullanıcı varsayılanı kabul edebilir ancak yol veya ortam tahmin ederek kuruluma başlama.

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
| **MCP_INTEGRATION** | `True` | Dış projelerden kasaya erişmek için editörlere (Claude Desktop, Cursor, Antigravity, Windsurf vb.) MCP kaydı yapma. |

---

## 3. Kurulum İcrası (Adım Adım)

Ajan olarak şu adımları terminal araçlarınla uygula:

### Adım 3.1: Kaynak ve Hedef Güvenlik Kontrolü
Kaynak repo yoksa yalnız `https://github.com/respected0/respectedbrain.git` adresinden temiz clone al. Hedefi mutlak yola çöz. Hedef doluysa şu ayrımı yap:

- `.respectedbrain-version` (veya desteklenen eski sürüm damgası) ile `.beyin/instructions.md` varsa bu geçerli mevcut vault'tur; aynı installer güvenli update yoluna geçer.
- Bu kimlik dosyaları yoksa hedef kullanıcıya ait bilinmeyen dolu klasördür; hiçbir dosya yazmadan dur ve açık hata raporla.

### Adım 3.2: Kanonik Installer'ı Çalıştır
Şablonu elle kopyalama, placeholder'ları elle değiştirme veya config JSON'unu kendin üretme. Bunların transactional ve rollback güvenli tek kaynak gerçekliği `installer/install.py` dosyasıdır.

Windows:
```powershell
python installer/install.py --non-interactive --vault-path "<VAULT_PATH>" --user-name "<USER_NAME>" --user-bio "<USER_BIO>" --companion "<COMPANION>" --os-name "<OS_NAME>" --provider <SUMMARY_PROVIDER> --priority <PROVIDER_PRIORITY...> --environment <native|wsl|hybrid> <OPTION_FLAGS>
```

Linux / macOS / WSL:
```bash
python3 installer/install.py --non-interactive --vault-path "<VAULT_PATH>" --user-name "<USER_NAME>" --user-bio "<USER_BIO>" --companion "<COMPANION>" --os-name "<OS_NAME>" --provider <SUMMARY_PROVIDER> --priority <PROVIDER_PRIORITY...> --environment <native|wsl|hybrid> <OPTION_FLAGS>
```

İlk çalıştırma temiz vault'u staged/transactional kurar. Aynı komut geçerli mevcut vault üzerinde yeniden çalıştırıldığında yönetilen dosyaları güvenli update yoluyla yeniler ve kullanıcı dosyalarını korur.

### Adım 3.3: Entegrasyon Drift Kontrolü
Kurulumdan sonra vault içindeki renderer ile kontrol yap:
```bash
python3 "<VAULT_PATH>/scripts/render_integrations.py" --root "<VAULT_PATH>" --check
```
Windows'ta doğrulanmış Python executable'ını `python3` yerine kullan. Exit code sıfır değilse kurulumu başarılı raporlama.

### Adım 3.6: İsteğe Bağlı Global Bağlantı
Kullanıcı global kurallara ve yeteneklere bağlanmak istiyorsa:
- Antigravity / Gemini için: `python runtime/scripts/install_antigravity_global.py`
- Claude / Codex / Cursor için: `python runtime/scripts/install_global.py`

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
python runtime/scripts/install_briefing_schedule.py "<VAULT_PATH>" --home "<KULLANICI_HOME>" --platform <windows-native | windows-wsl | linux | macos> --time "08:00" --apply
```

### Adım 3.9: Editörlere MCP Sunucusunu Kaydetme (İsteğe Bağlı)
Kullanıcı dış projelerde kod yazarken kasadaki hafızaya, kararlara ve notlara erişmek istiyorsa:
```bash
python "<VAULT_PATH>/scripts/vault_mcp_server.py" --vault "<VAULT_PATH>" --register
```
Bu komut sistemde kurulu Claude Desktop, Cursor IDE, Windsurf, Google Antigravity ve Claude Code ortamlarına `respected-vault` MCP sunucusunu güvenle kaydeder.

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
7. MCP sunucusunun editörlere kaydedilme durumu (Aktif: `respected-vault` veya Pasif).
