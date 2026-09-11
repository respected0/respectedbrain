# Respected Brain — Teknik Spesifikasyon ve Davranış Sözleşmesi

Durum: **Yetkili Teknik Sözleşme (Golden Standard)**<br>
Kaynak: `https://github.com/respected0/respectedbrain`<br>
Sürüm: `0.0.1` (`.beyin-version`, `.beyin-multi-version`)

Bu belge, Respected Brain sisteminin bileşen mülkiyetini, yaşam döngüsü kurallarını, platform çalışma profillerini ve doğrulama kapılarını belirleyen yetkili sözleşmedir (SSOT specification).

---

## 1. Temel Prensipler ve Kapsam

1. **Bağımsız ve Kendine Yeten (Self-Contained):** Respected Brain tamamen bağımsız bir projedir; harici bir fork veya upstream sync bağımlılığı barındırmaz.
2. **Çoklu Ajan Desteği:** Antigravity, Codex, Cursor ve Claude Code aynı Obsidian vault'unu ortak hafıza olarak kullanır. Claude zorunlu değildir; sistem dilediğiniz yapay zeka aracı ile tek başına veya birlikte çalışabilir.
3. **Tek Doğruluk Kaynağı (SSOT):** Tüm kurallar ve skill tanımları `template/.beyin/` altında tutulur. Agent entegrasyon dosyaları bu kaynaktan deterministik olarak üretilir.
4. **Platform Taşınabilirliği:** `portable` (POSIX/macOS/Linux), `windows-wsl` (Windows + WSL) ve `windows-native` (Native Windows / `py.exe -3`) profillerinin her biri eksiksiz test kapılarıyla korunur.
5. **Veri Güvenliği ve Geri Dönülebilirlik:** Vault Markdown dosyalarından oluşur. Güncellemeler öncesinde otomatik Git snapshot'ı ve Restic yedekleme desteği sağlanır.

---

## 2. Sürüm ve Dosya Mülkiyeti Sözleşmesi

### 2.1 Sürüm Damgası
- `.beyin-version`: `0.0.1` (Respected Brain birleşik sürümü)
- `.beyin-multi-version`: `0.0.1` (Geriye dönük uyumluluk damgası)
- Desteklenen Güncelleme Aralıkları: `0.0.1` öncesi tüm erken geliştirme sürümlerinden transactional yükseltme (`scripts/update_respected.py`) desteklenir.

### 2.2 Yönetilen Dosya Kategorileri (`scripts/respected_manifest.py`)

#### A. Üretilen Entegrasyon Dosyaları (`GENERATED`)
Bu dosyalar elle düzenlenmez; `scripts/render_integrations.py` tarafından üretilir:
- `AGENTS.md`
- `CLAUDE.md`
- `.claude/settings.json`
- `.codex/hooks.json`
- `.cursor/hooks.json`
- `.cursor/rules/beyin.mdc`
- `.agents/hooks.json`
- `.agents/rules/beyin.md`

#### B. Çekirdek Çalışma Zamanı (`RUNTIME`)
- Platform & Köprü: `.beyin/runtime_platform.py`, `.beyin/hooks/bridge.py`, `.beyin/hooks/lifecycle.py`, `.beyin/events.py`
- Arka Plan Motorları: `.beyin/engine/flush.py`, `.beyin/engine/compile.py`
- Yürütme & Analiz: `.beyin/model_runner.py`, `.beyin/map_builder.py`, `.beyin/morning_briefing.py`, `.beyin/graph_analysis.py`, `.beyin/graphrag.py`, `.beyin/session_brain.py`, `.beyin/session_viz.py`, `.beyin/bounded_recall.py`
- Hook Kabukları: `.claude/hooks/lib.sh`, `session-start.sh`, `prompt-counter.sh`, `session-end.sh`, `pre-compact.sh`, `post-compact.sh`, `session-stop-capture.ps1`, `session-stop-capture.sh`
- Kalite Kuralları: `.agents/rules/software-quality-1.md`, `.agents/rules/software-quality-2.md`, `.cursor/rules/software-quality-1.mdc`, `.cursor/rules/software-quality-2.mdc`
- Şablonlar: `📋 Templates/Base.base`, `📋 Templates/Canvas.canvas`
- Dağıtılan Yönetim Scriptleri: `scripts/render_integrations.py`, `legacy_names.py`, `install_antigravity_global.py`, `install_global.py`, `install_briefing_schedule.py`, `set_summary_provider.py`, `repair_daily.py`, `backup_restic.py`, `publish_git_snapshot.py`, `arama.py`, `vault_mcp_server.py`, `mine_agent_history.py`, `defuddle.py`, `url_safety.py`, `vault_linter.py`, `architect_scan.py`, `smart_merge.py`, `tiling_check.py`

#### C. Skill Hedef Yolları (`SKILL_DESTINATIONS`)
- `.beyin/skills`
- `.claude/skills`
- `.agents/skills`

#### D. Yalnızca Repo Araçları (`REPO_ONLY_SCRIPTS`)
- `install-windows.ps1`
- `enable_multiai.py`
- `upstream_sync.sh`

---

## 3. Sağlayıcı Seçimi ve Hata Toleransı

`.beyin/config.json` içindeki `summary_provider` anahtarı arka plan oturum özetleyicisini yönetir.

| Değer | Davranış | Fallback Sırası |
| --- | --- | --- |
| `auto` (Varsayılan) | Hook'u tetikleyen agent'ın CLI'ını ilk sıraya alır. | `agy` → `codex exec` → `cursor-agent -p` → `claude -p` |
| `antigravity` | İlk olarak Google Antigravity CLI (`agy`) denenir. | Kurulu ve giriş yapılmış diğer CLI'lar. |
| `codex` | İlk olarak OpenAI Codex CLI (`codex exec`) denenir. | Kurulu ve giriş yapılmış diğer CLI'lar. |
| `cursor` | İlk olarak Cursor CLI (`cursor-agent -p`) denenir. | Kurulu ve giriş yapılmış diğer CLI'lar. |
| `claude` | İlk olarak Claude Code CLI (`claude -p`) denenir. | Kurulu ve giriş yapılmış diğer CLI'lar. |

### Hata Yönetimi Kuralları
- **Geçici Hatalar:** CLI bulunamaması, zaman aşımı (timeout), HTTP 429 / kota tükenmesi, geçici 502/503/504 sunucu hatalarında süreç sonlandırılmaz; bir sonraki uygun sağlayıcıya geçilir.
- **Kalıcı Hatalar:** Kimlik doğrulama (auth) veya yapılandırma hatalarında sessizce başka araca geçilmez; hata geliştiriciye açıkça raporlanır.
- **Ortam Değişkenleri:** `BEYIN_MODEL_PROVIDER` geçici sağlayıcı override'ı, `BEYIN_LLM_COMMAND` ise prompt'u stdin üzerinden alan özel komut override'ıdır.

---

## 4. Platform Çalışma Profilleri ve Sınırları

### 4.1 `windows-wsl` (Windows + WSL)
- IDE Windows tarafında çalışırken hook `wsl.exe --cd <vault>` ile WSL içindeki Python 3 ortamını tetikler.
- Vault yolu `/mnt/<drive>/...` formatına normalize edilir.
- Obsidian vault'u doğrudan Windows dosya yolundan açar.

### 4.2 `windows-native` (Native Windows)
- WSL veya POSIX Bash katmanı gerektirmez.
- `py.exe -3` mutlak Windows dosya yollarını (`C:\...`) kullanarak `.beyin/hooks/bridge.py` dosyasını çalıştırır.
- Kurulum `scripts/install-windows.ps1` ile yapılır; Python 3, Git ve seçilen CLI yürütücüleri doğrudan test edilir.

### 4.3 `portable` (macOS / Linux)
- Standart POSIX shell ve Python 3 ile çalışır.
- Linux için XDG masaüstü entegrasyonu, macOS için LaunchAgent arka plan zamanlayıcısı desteklenir.

---

## 5. Yaşam Döngüsü ve İşleme Sözleşmesi

### 5.1 Oturum Başlangıcı ve Bağlam Enjeksiyonu
1. `map_builder.py` çalışarak `Vault-Map.md` ve `Skills-Map.md` dosyalarını metadata üzerinden üretir. İnsan tarafından yazılmış dosyalara dokunulmaz; symlink saldırılarına karşı fail-closed davranılır.
2. Bağlam enjeksiyonu (`Last-Session.md`, `Threads.md`, `Kurallar.md` ilk 60 satır, son Journal girdisi, haritalar, bilgi indeksi ve günlükler) oluşturulur.
3. Toplam bağlam **16.000 karakterlik üst sınırla (bounded recall)** sınırlandırılır.

### 5.2 Oturum Kapanışı ve Flush (`flush.py`)
1. Stdin veya transkript yolu alınarak asenkron `flush.py` süreci başlatılır; IDE gecikmesiz döner.
2. Modelden dönen özet 5 sabit Türkçe başlık (`## 1. Oturum Özeti` ... `## 5. Sonraki Adımlar`) için doğrulanır.
3. Eksik veya geçersiz özetler reddedilir. Geçerli özet `daily/YYYY-MM-DD.md` dosyasına atomik eklenir.

### 5.3 Bilgi Tabanı Derlemesi (`compile.py`)
1. Derleme sabah 08:00 zamanlanmış pipeline'ı tarafından veya SessionStart catch-up sırasında tetiklenir.
2. İçinde bulunulan günün daily dosyası derlemeye alınmaz (`--before-date` kuralı).
3. Derleme işlemi vault dışında, işletim sisteminin `0700` izinli geçici dizininde izole staging'de yürütülür.
4. Yalnızca onaylı yollar (`knowledge/index.md`, `knowledge/log.md`, `knowledge/concepts/*.md`, `knowledge/connections/*.md`) vault'a atomik olarak aktarılır.

---

## 6. Güncelleme ve Transactional Güvenlik Sözleşmesi

Vault güncellemeleri `scripts/update_respected.py` tarafından transactional olarak yürütülür:
1. **Pre-flight Kontrolleri:** Hedefin geçerli bir Respected Brain vault'u olduğu doğrulanır. Temiz olmayan çalışma ağaçlarında işlem durdurulur.
2. **Yedekleme:** Değişecek dosyaların Git commit'i veya harici bir kopyası (`~/.respected-brain-yedek/`) alınır.
3. **Staging:** Tüm güncellenen dosyalar vault dışında hazırlanır.
4. **Atomik Uygulama:** Dosyalar yerlerine taşınır.
5. **Damgalama:** Tüm kontroller geçtikten sonra `.beyin-multi-version` ve yetkili `.beyin-version` atomik olarak güncellenir.
6. **Onarım (`--force`):** Damga veya dosya tutarsızlığı olan vault'lar `--force` bayrağı ile tutarlı `0.0.1` durumuna getirilebilir.

---

## 7. Kalite ve Doğrulama Kapıları

Tüm değişiklikler şu üç kapıdan geçmek zorundadır:

```bash
# 1. Entegrasyon ve SSOT doğrulaması
python3 scripts/render_integrations.py --check

# 2. Tam regresyon ve platform doğrulama paketi
python3 tests/run_all.py

# 3. Git boşluk ve biçim denetimi
git diff --check
```

Testler gerçek ağ veya model çağrısı yapmaz; tüm sağlayıcılar stub'lar ve geçici vault'lar üzerinden Zero-Trust test modeline tabi tutulur.
