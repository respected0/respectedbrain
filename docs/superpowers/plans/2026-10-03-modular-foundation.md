# Modular Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mevcut işlevleri koruyarak tek paket ve birbirinden bağımsız program/veri/not kasası yerleşimine geçmek.

**Architecture:** Önce saf paket/yol/config sözleşmesi kurulur, sonra mevcut algoritmalar bu bağlama taşınır. Entegrasyonlar tek CLI'a bağlanır; kurulum ve migration aynı sahiplik, işlem günlüğü ve geri alma hizmetlerini kullanır. Bu tek, sıralı planın görevleri boyut nedeniyle üç ek dosyadadır; ekler bağımsız plan değildir.

**Tech Stack:** Python, stdlib unittest/argparse/importlib.resources/sqlite3, setuptools wheel, PyInstaller onedir, Inno Setup, PowerShell ve POSIX kabukları. Mevcut Python 3.10+ desteği korunur (`requires-python = ">=3.10"`); kaynak/wheel CI 3.10 ve 3.13, frozen build 3.13. Yeni işlev bağımlılığı eklenmez; build araçları geliştirme bağımlılığıdır.

**Spec:** [Ana sözleşme](../specs/2026-10-03-modular-foundation-design.md) ve [kurulum/geçiş sözleşmesi](../specs/2026-10-03-modular-foundation-operations.md), kullanıcı onayı 2026-10-03.

scope: project; confidence: inferred; supersedes: []; status: plan-review (as of 2026-10-03).

## Global Constraints

- Windows AppRoot: `%LOCALAPPDATA%/Programs/RespectedBrain`.
- Windows DataRoot: `%LOCALAPPDATA%/RespectedBrain`.
- Varsayılan VaultRoot: `Documents/RespectedOS`; mevcut kasa taşınmaz.
- macOS AppRoot: `~/Applications/RespectedBrain.app`; DataRoot: `~/Library/Application Support/RespectedBrain`.
- Linux AppRoot: `~/.local/lib/respectedbrain`; launcher: `~/.local/bin/respectedbrain`; DataRoot: `$XDG_DATA_HOME/respectedbrain` veya `~/.local/share/respectedbrain`.
- Windows Known Folders ve Documents yönlendirmesi kullanılır; kullanıcı adı sabitlenmez.
- Tek `respectedbrain` paketi, tek CLI, tek aktif motor; Windows kullanıcıya Python kurdurmaz.
- PyInstaller onedir içerik klasörü `app`; kaynaklar `app/respectedbrain/resources`.
- Program çalışırken AppRoot'a teknik veri yazılmaz; DataRoot yürütülebilir ürün kodu içermez.
- Config ve marker şeması `3`; kalıcı kasa UUID'si yol hash'i değildir.
- Kasa seçimi: açık `--vault`/`--vault-id`, `RESPECTED_VAULT_PATH`, `active_vault_id`.
- İki selector hata; açık geçersiz selector başka kasaya fallback yapmaz.
- `RESPECTED_APP_DIR`/`RESPECTED_DATA_DIR` açık override; `RESPECTED_RUNTIME_DIR` yalnız legacy girişidir.
- Import sırasında keşif, mkdir, kullanıcı config okuma/yazma veya subprocess çalıştırma yapılmaz.
- core feature import etmez; özellikler CLI modülünü import etmez.
- Paket defaults kullanıcı config'inin üzerine kopyalanmaz; config atomik ve kayıp güncelleme olmadan yazılır.
- Kullanıcı config'i > geçerli legacy tercihler > paket defaults; bilinmeyen alanlar korunur.
- Instructions/skills kişiselleştirmeleri UUID'ye bağlı `overrides/` altında korunur.
- Global/MCP/zamanlayıcı yalnız desired-state ile açılır; kapalı seçenek kapalı kalır.
- Hook/MCP stdout protokol içindir; tanılama stderr/DataRoot logs kullanır.
- Migration varsayılan dry-run; değişiklik için `--apply` gerekir.
- Bilinmeyen dosyalar kullanıcıya aittir; temizleme manifest ve değişmemiş hash ister.
- Güncelleme/onarım/kaldırma kullanıcı notlarını ve `.obsidian` dosyalarını değiştirmez.
- Uninstall DataRoot'u varsayılan korur; açık `--purge-data` bile kasaya dokunmaz.
- Inno AppId `{870D0E4C-87A0-4A3C-9A82-F8E3C3A19C1D}` korunur; `UsePreviousAppDir=no`; uninstaller `AppRoot/uninstall`.
- Eski geniş temizlik yapan uninstaller çalıştırılmaz; rollback başka ajanın yeni dosyasını silmez.
- Önceki çalışma ağacı düzeltmeleri taşınan güncel dosyalarda korunur.
- Yeni ürün özelliği, portable/system-wide kurulum, mikroservis veya plugin yöneticisi eklenmez.
- Canlı kurulum ancak geçici kasa ve paket kontrollerinden sonra, son devreye alma adımında ele alınır.

## Review Focus

1. Türkçe/emoji/boşluklu yol, yönlendirilmiş Documents, yanlış CWD ve iki kasa: doğru UUID seçilir, geçersiz açık seçim hata verir. Görev 2–3.
2. Kasa taşınması/kopyalanması ve iki süreçten config güncellemesi: UUID korunur, kopya çakışır, iki değişiklik de kalır. Görev 3.
3. Kapalı global/MCP/schedule, özel provider tercihi ve değiştirilmiş instructions/skills: geçiş bunları korur. Görev 8, 11–12.
4. State çakışması, aktif yazıcı, junction/symlink ve sahipli dosyanın envanterden sonra değişmesi: etkinleştirme durur, bilinmeyen dosya korunur. Görev 9, 11–12.
5. Her işlem aşamasında hata ve Windows'ta kullanımda executable: geri alma kanıtlanır; not hash'leri ve eşzamanlı kullanıcı dosyaları korunur. Görev 10, 12–13.

---

## Kullanıcı için uygulama sırası

1. **Görev 1–3:** Tek paket, ortak yollar ve kasa kimliği.
2. **Görev 4–7:** Şu anki işlevlerin yeni modüllere taşınması ve tek komut.
3. **Görev 8–10:** AI bağlantıları, kurulum, güncelleme ve kaldırma.
4. **Görev 11–13:** Eski kurulumun güvenli dönüşümü ve gerçek dağıtım paketi.
5. **Görev 14:** Gerçek bilgisayarda önce önizleme, sonra denetlenen devreye alma.

## Dosya haritası

Tüm yollar repo köküne göredir. Kaynak→hedef envanteri spec §5'tir; burada
tam hedef dosya adları ve sahip görevler sabitlenir. Taşınan dosyanın güncel
disk içeriği kullanılır; eski commit'ten içerik alınmaz.

| Görev | Yeni/değişen dosyalar ve sorumluluk |
| --- | --- |
| 1 | `pyproject.toml`, `src/respectedbrain/{__init__,__main__,cli}.py`: metadata/dispatcher; `core/resources.py`: salt okunur kaynak erişimi; `resources/`: template, defaults, instructions, skills, integrations, gateway/web; `tests/foundation_support.py`: geçici kasa ve hash yardımcıları; `tests/package_contract_test.py`: wheel/import sınırı |
| 2 | `core/{paths,platform,context,errors}.py`: saf yol/bağlam/hata; `tests/foundation_paths_test.py` |
| 3 | `core/config.py`, `vault/registry.py`: kilitli config ve UUID kaydı; `tests/vault_registry_test.py` |
| 4 | `providers/runner.py`; `memory/{flush,compile,lifecycle,session_brain,session_viz,bounded_recall,events}.py`, `memory/graph/{graph_analysis,graphrag}.py`; `tests/foundation_memory_test.py` |
| 5 | `briefing/service.py`, `search/engine.py`, `vault/maps.py`; `tests/foundation_features_test.py` |
| 6 | `gateway/server.py`, `orchestration/{runner,orchestrate,antigravity_orchestrator}.py`; `maintenance/{repair_daily,vault_linter,architect_scan,smart_merge,tiling_check}.py`; `maintenance/backup/{backup_restic,publish_git_snapshot}.py`; `maintenance/ingestion/{mine_agent_history,defuddle,url_safety}.py`; `tests/foundation_services_test.py` |
| 7 | `cli.py`, `core/bootstrap.py`: tek composition root/komutlar; `tests/foundation_cli_test.py` |
| 8 | `integrations/hooks/{bridge,codex_notify}.py`, `integrations/mcp/server.py`, `integrations/global_config/{service,codex,claude,gemini,antigravity}.py`, `integrations/scheduling/service.py`, `integrations/{rendering,backend}.py`; `tests/foundation_integrations_test.py` |
| 9 | `installation/{ownership,transaction,setup,wizard}.py`; `tests/foundation_setup_test.py` |
| 10 | `installation/{update,repair,uninstall}.py`; `tests/foundation_operations_test.py` |
| 11 | `installation/{legacy,migration}.py`; `tests/foundation_migration_preview_test.py` |
| 12 | `installation/migration.py`; `tests/foundation_migration_apply_test.py` |
| 13 | `packaging/windows/{respectedbrain.spec,respected_setup.iss,install.ps1}`, `packaging/macos/setup.command`, `packaging/linux/setup.sh`; `tools/{build_installer.py,upstream_sync.sh,verify_distribution.py}`; `.github/workflows/{ci,release}.yml`; `tests/foundation_distribution_test.py`; mevcut smoke/native/PS1/shell testleri; README ve rehberler |
| 14 | Yeni ürün kodu yok; kullanıcıya sunulan canlı envanter, backup ve doğrulama raporu |

Her paket alt dizininde yan etkisiz `__init__.py` bulunur. `runtime/instructions.md`
→ `resources/instructions/default.md`; `runtime/config.json` → `resources/defaults.json`.
`runtime/adapters/` kaynak tanımları → `resources/integrations/`; üretilmiş provider
ayarları paket kaynak tanımıyla karıştırılmaz. `runtime/scripts/enable_multiai.py`
→ görev 8'de rendering/global_config hizmetlerine delegasyon; yeni algoritma yok.
`setup.py`, `setup`, `setup.command`, `installer/*.py` ve eski doğrudan CLI
dosyaları yalnız bir geçiş sürümü için ince yönlendirme olabilir; ürün mantığı
hedef dosyalarda kalır. `runtime_hub.py` kopyalarının yerine yalnız `core/paths.py`
geçer. Kökteki `setup.exe` source control'den çıkar; yeni çıktı `dist/` olur.

## Ortak doğrulama ve çalışma disiplini

Uygulama başlangıcında `using-git-worktrees` ile izolasyon oluştur. Şu anki
kirli çalışma ağacı için önce `git status --short`, `git diff --binary` ve
`tests/runtime_layout_test.py` içeriğini güvenli workspace snapshot'ına al.
Yeni worktree'ye takip edilen diff'i `git apply` ile ve takip edilmeyen testi
birebir kopyalayarak aktar; hash/diff karşılaştır. Ana checkout'u resetleme.
Bu taban doğrulanmadan taşıma başlatma. Üretilmiş mevcut `setup.exe` kaynak
olarak yeniden üretimde kullanılmaz; snapshot'ta korunur.

PowerShell'de `$py` ve `$pwsh` gerçek çalıştırıcıya atanır. Bu makinede Python:
`C:/Users/Furkan/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`.
Yeni worktree'de `.venv` oluştur ve `$py` değerini `.venv/Scripts/python.exe`
yap; POSIX eşdeğeri `.venv/bin/python`. CI `python` kullanır.

Başlangıç: `& $py -m unittest discover -s tests -p '*test*.py'` çıktısını kaydet;
önceki 447/10 tarihsel ölçümdür, yeni koşuda aynı sayı zorunlu değildir.
Her görevde yeni anlamlı test önce FAIL, sonra OK olur; regresyon modülleri
aynı davranışı paket importlarıyla sınar. Eski konumun varlığını bekleyen
testler yeni sözleşmeye çevrilir; davranış testi sırf taşıma için silinmez.
Her commit'te yalnız o görevin dosyalarını stage et, `git diff --cached --check`
çalıştır; `git add .` kullanma.

`tests/foundation_support.py` sadece stdlib kullanır:
`snapshot(root: Path) -> dict[str, str]` dizin/symlink/dosya SHA256 envanteri;
`note_hashes(vault: Path) -> dict[str, str]` daily, knowledge, Companion,
proje, Templates, `.obsidian` dosyaları; `write_json(path: Path, value: dict) -> None`;
`run_cli(argv: list[str], *, env: dict[str,str], cwd: Path) -> CompletedProcess[str]`.
Test sınıfları TemporaryDirectory içinde `app`, `data`, `Türkçe 🧠 Vault`,
`İkinci Vault` yollarını oluşturur; gerçek HOME/AppData/provider config/task
kullanılmaz. Gerçek native kayıt testleri yalnız geçici kullanıcı dosyası ve
benzersiz task adıyla, finally temizliğiyle çalışır.

## Görev ekleri

- [Görev 1–5: paket, bağlam ve temel işlevler](2026-10-03-modular-foundation-core.md)
- [Görev 6–10: hizmetler, entegrasyon ve kurulum](2026-10-03-modular-foundation-services.md)
- [Görev 11–14: migration, dağıtım ve devreye alma](2026-10-03-modular-foundation-delivery.md)

## Plan öz incelemesi

Spec §1–5 → görev 1, 4–6, 13; §6 → görev 2–3; §7/operations §1 → görev
7–8; operations §2–3 → görev 9–10; operations §4 → görev 11–12; operations
§5 → görev 13–14. Beş Review Focus koşulunun sahip testleri eklerde isimli
assertion'larla bulunur. Kaynakların tamamı dosya haritasında/spec eşleştirmesinde
bir göreve atanmıştır; `enable_multiai.py` envanterde ayrıca kapatılmıştır.
İmzalar ortak AppPaths/AppContext ve isimli sonuç tipleriyle tutarlıdır.
Öz incelemede olmayan `repair_daily --check` seçeneği kaldırıldı; mevcut
salt okunur `vault_linter --json` kullanıldı. Python sürüm tabanı mevcut
README'deki 3.10+ ile eşlendi, sürüm tabanı yükseltilmedi.

## For future agent

Spec onaylandı, bu plan kullanıcı incelemesini ve yürütme yöntemi seçimini
bekliyor. Görev eklerini sırayla uygula; çalışma ağacındaki onarımları koru.
Canlı kurulum değişikliğine görev 14'ün önizleme ve geri alma kontrolleri
tamamlanmadan geçme.
