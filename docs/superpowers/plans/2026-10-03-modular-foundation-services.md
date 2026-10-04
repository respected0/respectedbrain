# Modüler temel — görev 6–10

Bu dosya [ana uygulama planının](2026-10-03-modular-foundation.md) sıralı
görev ekidir; görev 1–5 tamamlanınca uygulanır. Global Constraints ve Review
Focus geçerlidir. scope: project; confidence: inferred; supersedes: [].

## Görev 6: Panel, orkestrasyon ve bakım sınırları

**Files:** Move: ana haritada görev 6 dosyaları/spec §5 karşılıkları;
Modify: `tests/{any_to_any_orchestrator,antigravity_orchestrator,smart_tools,
repair_daily,backup_and_snapshot,adversarial_quality}_test.py`;
Create: `tests/foundation_services_test.py`.

**Interfaces:** Consumes: AppContext, ModelService, SearchEngine.
Produces: `gateway/server.py: start_server(ctx: AppContext, *, port: int = 8520, open_browser: bool = False) -> None`;
`orchestration/runner.py: run(ctx: AppContext, *, project_root: Path, argv: Sequence[str]) -> int`;
`maintenance/__init__.py: run_tool(ctx: AppContext, *, name: str, argv: Sequence[str]) -> int`.
`name` izinli mevcut araçlar: repair_daily, vault_linter, architect_scan,
smart_merge, tiling_check, backup_restic, publish_git_snapshot,
mine_agent_history, defuddle; url_safety çağrılan saf yardımcıdır.

- [ ] **1. Test yaz:** `FoundationServicesTest.test_gateway_config_is_user_config_even_without_legacy_tree`,
  `test_orchestration_project_is_not_vault`, `test_tools_do_not_write_app_root`.
  HTTP server testleri port 0 ve loopback kullanır; subprocess/model fake.

```python
self.assertEqual(gateway_config['summary_provider'], 'codex')
self.assertEqual(orchestrator_worktree_root.parent, self.code_project)
self.assertNotEqual(orchestrator_worktree_root.parent, self.vault)
self.assertEqual(snapshot(self.app), before_app)
self.assertEqual(snapshot(self.vault2), before_vault2)
self.assertEqual(run_tool(ctx, name='vault_linter', argv=['--json']), 0)
```

- [ ] **2. FAIL doğrula:** `& $py -m unittest -v tests.foundation_services_test`;
  context kabul etmeyen eski giriş/import hatası.
- [ ] **3. Hizmetleri taşı:** panel statikleri ResourceCatalog'dan; config
  değişimi ConfigStore update ile; provider/status/orkestrasyon işleri ilgili
  hizmetle. Gateway doğrudan provider subprocess veya cleanup çalıştırmaz.
  Orkestrasyonun code project kökü açık parametredir. Bakım araçlarının mevcut
  CLI seçenekleri/koruma davranışı korunur; teknik lock/temp/log DataRoot'ta,
  kullanıcıca açık seçilen backup/publish hedefleri mevcut sözleşmesinde kalır.
  `run_tool` mevcut modüllerin ctx alan ince çağrılarını dağıtır; algoritma
  tekrar edilmez. Salt okunur test için sağlıklı minimal kasa ve mevcut
  `vault_linter --json` kullanılır; repair_daily'ye yeni seçenek eklenmez.
- [ ] **4. PASS doğrula:** yeni test ve Files'taki altı mevcut unittest
  modülünü `& $py -m unittest -v` ile çalıştır; OK. HTTP test server'ını
  finally kapat; CI'da browser açılmaz.
- [ ] **5. Commit:** görev 6 kaynakları/testleri/eski girişleri stage et;
  `git diff --cached --check`; `git commit -m "refactor: bind gateway orchestration and maintenance to services"`.

## Görev 7: Tek CLI ve composition root

**Files:** Modify: `src/respectedbrain/cli.py`; Create:
`bootstrap.py`, `tests/foundation_cli_test.py`;
Modify: `tests/{scripts,windows_native,runtime_platform}_test.py`.

**Interfaces:** Consumes: görev 2–6 hizmetleri.
Produces: `bootstrap.py: bootstrap(*, vault: Path | None = None, vault_id: str | None = None, env: Mapping[str,str] | None = None) -> AppContext`;
`launcher_argv(*, env: Mapping[str,str] | None = None) -> tuple[str,...]`;
`cli.main(argv: Sequence[str] | None = None) -> int` aynı giriş olmaya devam eder.
Frozen launcher `(sys.executable,)`, geliştirme `(sys.executable,'-m','respectedbrain')`;
kurulu POSIX kayıtları stable `respectedbrain` launcher kullanır (görev 8).

- [ ] **1. Test yaz:** `FoundationCliTest.test_module_and_entrypoint_dispatch_identically`,
  `test_vault_selector_validation`, `test_existing_features_have_one_dispatcher`.
  Dispatcher hizmetlerini mock ile kaydet; sonraki görevlerin servislerini
  ilgili CLI handler yazıldığında tamamla, başarı döndüren boş stub bırakma.

```python
self.assertEqual(module_result.returncode, entry_result.returncode)
self.assertEqual(module_result.stdout, entry_result.stdout)
self.assertEqual(invalid_selector.returncode, 2)
self.assertEqual(both_selectors.returncode, 2)
self.assertEqual(compile_call.ctx.paths.vault_id, self.uuid)
self.assertEqual(missing_registration.returncode, 2)
self.assertEqual(snapshot(self.vault2), before_vault2)
```

- [ ] **2. FAIL doğrula:** `& $py -m unittest -v tests.foundation_cli_test`;
  compile/vault handler yokluğu beklenir.
- [ ] **3. Dispatcher uygula:** argparse ortak selector doğrulaması;
  configure ConfigStore, vault register/list/discover VaultRegistry,
  dashboard/briefing/compile ilgili ctx hizmetlerini çağırır. Mevcut arama,
  orchestration ve bakım CLI işlevlerini `search`, `orchestrate`, `maintenance`
  alt komutlarıyla koru; burada yeni algoritma yok. Hook/MCP görev 8, setup/
  update/repair/uninstall görev 9–10, migrate görev 11–12 handler'larını
  servisleriyle birlikte ekle. Arg/selection hata 2, işlem hata 1, başarı 0.
  Kaynak sürümü metadata'dan; logging kurulumu yalnız başlangıçta stderr/log.
- [ ] **4. PASS doğrula:** aynı unittest komutu ve Files'taki üç mevcut
  modül; OK. `& $py -m respectedbrain --help` ve `--version` normal çıktı,
  boş kayıtla vault komutu kullanıcıya registration gerektiğini söyler.
- [ ] **5. Commit:** görev 7 dosyalarını stage et;
  `git diff --cached --check`; `git commit -m "feat: dispatch existing workflows through one CLI"`.

## Görev 8: Tek başlatıcıya bağlı entegrasyonlar

**Files:** Move/create: ana haritada görev 8 dosyaları;
Modify: `cli.py`, `resources/integrations/`,
`tests/{profile_render,multiai,mcp_registration,global_brand_migration,
briefing_schedule}_test.py`, `tests/briefing_schedule_windows_test.ps1`,
`tests/hooks_test.sh`; Create: `tests/foundation_integrations_test.py`.

**Interfaces:** Consumes: AppContext, ConfigStore, launcher_argv, handle_event.
Produces (`integrations/backend.py`):
`ExternalChange(kind: str, key: str, before: bytes | None, after: bytes | None)`;
`IntegrationBackend` Protocol: `read(kind: str,key: str) -> bytes | None`,
`apply(change: ExternalChange) -> None`, `restore(change: ExternalChange) -> None`,
`quiesce(vault_id: str | None) -> ContextManager[None]`;
`IntegrationProfile(platform: Literal['windows-native','posix','windows-wsl'], launcher: tuple[str,...], user_home: Path)`;
`integrations/rendering.py: plan_integrations(ctx: AppContext, profile: IntegrationProfile, desired: Mapping[str,bool], backend: IntegrationBackend) -> tuple[ExternalChange,...]`;
`integrations/hooks/bridge.py: dispatch(ctx: AppContext, *, provider: str, event: str, argv: Sequence[str], stdin: str) -> str`;
`integrations/mcp/server.py: serve(ctx: AppContext) -> int`.
Desired anahtarları `global`, `mcp`, `schedule`, `shortcut`; provider özel
ayarlar config integrations içinde korunur. Üretilmiş metadata ownership
için kaynak launcher/UUID ve önceki byte snapshot taşır. Backend kind izinli
değerleri `file`, `mcp`, `task`, `shortcut`, `registry`; quiesce None bütün
kayıtlı ürün yazıcılarını, UUID yalnız o kasayı kapsar; başka uygulama
süreçlerine müdahale etmez. user_home yalnız
test/config hedefini belirler, paket konumu sayılmaz.

- [ ] **1. Test yaz:** `FoundationIntegrationsTest.test_disabled_options_produce_no_new_registration`,
  `test_native_and_explicit_wsl_argv`, `test_protocol_stdout_and_existing_user_blocks`.
  Sahipli olmayan Codex notify chain, kullanıcı CLAUDE/AGENTS blokları ve
  MCP kayıtları fixture olsun. Kayıt yanlış launcher'a çevrilmişse restore
  başka uygulamanın kayıtlarını zorla ezmesin.

```python
self.assertEqual(plan_integrations(ctx, profile, all_false, backend), ())
self.assertEqual(native_hook_argv[0], str(self.app / 'respectedbrain.exe'))
self.assertIn(self.uuid, native_hook_argv)
self.assertNotIn('python', native_hook_argv)
self.assertEqual(wsl_transcript, '/mnt/c/Users/Test/Türkçe 🧠 Vault/turn.jsonl')
self.assertEqual(updated_user_block, original_user_block)
self.assertEqual(json.loads(mcp_stdout)['jsonrpc'], '2.0')
self.assertNotIn('DEBUG', mcp_stdout)
```

- [ ] **2. FAIL doğrula:** `& $py -m unittest -v tests.foundation_integrations_test`;
  yeni renderer/launcher/ctx imza hatası.
- [ ] **3. Taşı ve bağla:** bridge mevcut provider argv/stdin/transcript ve
  event normalizasyonunu korur; notify chaining ve session id aynı kalır.
  MCP mevcut tools şemasını kullanır. Global ayarlarda yalnız yönetilen blok;
  Antigravity/global/multiai tek hizmete delege edilir. Provider render
  önce UUID overrides, sonra paket default kullanır. Plan salt okunur,
  apply görev 9 transaction içinde backend ile olur. Native Windows'ta
  sistem Python/WSL yok; seçilmiş WSL profile launcher'ı WSL içinde doğrula,
  yoksa kayıt hata. Sadece yol tipindeki argv dönüştürülür, JSON metni değil.
  POSIX shell quoting ve Windows argv quoting provider formatına göre yapılır.
  Schedule tek installed launcher + briefing + UUID; kapalı kayıt yaratılmaz.
- [ ] **4. PASS doğrula:** yeni ve Files'taki mevcut testler; ayrıca
  `& $pwsh -NoProfile -File tests/briefing_schedule_windows_test.ps1` ve
  POSIX ortamda `bash tests/hooks_test.sh`; OK. Native test unique task
  adıyla çalışır; WSL bulunmazsa yalnız gerçek WSL smoke gerekçesiyle atlanır.
- [ ] **5. Commit:** görev 8 dosyalarını stage et;
  `git diff --cached --check`; `git commit -m "refactor: register integrations against stable launcher and vault UUID"`.

## Görev 9: Sahiplik, işlem günlüğü ve ortak setup

**Files:** Create/move: `installation/{ownership,transaction,setup,wizard}.py`;
Modify: `cli.py`, `tests/{wizard,vault_hygiene,e2e_fresh_install_linux}_test.py`;
Create: `tests/foundation_setup_test.py`. Eski installer/install.py ve
setup_wizard algoritmaları tek setup hizmetine geçer.

**Interfaces:** Consumes: Roots, Registry, ResourceCatalog, IntegrationBackend/profile/plan.
Produces (`ownership.py`): `OwnedFile(path: Path, sha256: str, role: str)`;
`OwnershipManifest(schema_version: int, files: tuple[OwnedFile,...], external: tuple[ExternalChange,...])`;
`prove_ownership(path: Path, manifest: OwnershipManifest) -> bool`;
(`transaction.py`): `OperationResult(success: bool, tx_id: str, conflicts: tuple[str,...])`;
`Transaction(data_root: Path, backend: IntegrationBackend, *, vault_id: str | None = None, fault: Callable[[str],None] | None = None)`
context manager, `backup(path: Path) -> None`, `replace(source: Path,target: Path) -> None`,
`apply_external(change: ExternalChange) -> None`, `commit() -> OperationResult`;
(`setup.py`): `setup(roots: Roots, vault: Path, *, profile: Mapping[str,str], desired: Mapping[str,bool], backend: IntegrationBackend, package: Path | None = None) -> OperationResult`.
`package=None` yalnız zaten yerleştirilmiş doğrulanmış uygulamada ilk setup;
paket yok/bozuksa başarı olmaz. GUI aynı setup hizmetini çağırır.

- [ ] **1. Test yaz:** `FoundationSetupTest.test_fresh_setup_is_pure_vault`,
  `test_nonempty_unregistered_target_is_untouched`,
  `test_manifest_does_not_own_user_notes`, `test_busy_writer_blocks_activation`.
  Template placeholders profile ile dolsun; idempotent ikinci setup user
  Core/Kurallar değişikliğini korusun. Fake backend gerçek writer lock taklit
  etmeye ek olarak child process lock testi kullansın.

```python
self.assertFalse((self.vault / '.beyin').exists())
self.assertFalse((self.vault / 'unins000.exe').exists())
self.assertEqual(marker['schema_version'], 3)
self.assertEqual(config['schema_version'], 3)
self.assertEqual(config['integrations']['schedule'], False)
self.assertEqual(note_hashes(self.existing_vault), before_notes)
self.assertEqual(snapshot(self.nonempty_target), before_target)
self.assertFalse(any(item.role == 'note' for item in manifest.files))
with self.assertRaises(BusyError):
    with Transaction(self.data, backend) as tx:
        tx.replace(self.staged_app, self.app)
```

- [ ] **2. FAIL doğrula:** `& $py -m unittest -v tests.foundation_setup_test`;
  setup/transaction henüz yok, import hatası.
- [ ] **3. Uygula:** stage template placeholder rendering, validate ve
  boş hedefe promote; mevcut kayıtlı kasa yalnız kaydedilir, template ile
  overwrite edilmez. Marker/config UUID registration hizmetiyle. Manifest
  uygulama dosyası SHA256 + external before/after içerir; notlar sahipli
  payload değildir. Transaction lock, quiesce, backup ve write-ahead journal
  DataRoot/backups/tx-id altında; boundary resolve/reparse kontrolü her
  mutasyonda yenilenir. Rollback yalnız kendi yazdığı ve hâlâ beklenen hash'i
  taşıyan hedefi geri alır; kullanıcı değişmiş hedef conflict olarak korunur.
  Registry/config yazıları da transaction backup ile kapsanır. Subprocess/
  GUI alt hata başarıya çevrilmez; startup recovery unfinished journal okur.
- [ ] **4. PASS doğrula:** yeni ve Files'taki üç mevcut test;
  `& $py -m unittest -v tests.foundation_setup_test tests.wizard_test tests.vault_hygiene_test tests.e2e_fresh_install_linux_test`;
  OK (platforma özel olan gerekçeli skip). Setup CLI ve GUI mock aynı
  hizmet parametrelerini üretir; ayrı cleanup algoritması yok.
- [ ] **5. Commit:** görev 9 dosyalarını stage et;
  `git diff --cached --check`; `git commit -m "feat: install pure vaults through ownership-aware transactions"`.

## Görev 10: Update, repair ve uninstall aynı güvenlik sınırında

**Files:** Move/create: `installation/{update,repair,uninstall}.py`;
Modify: `cli.py`, `tests/{update_cli,update_respected,auto_updater,uninstall}_test.py`;
Create: `tests/foundation_operations_test.py`.

**Interfaces:** Consumes: AppContext, Transaction, manifest, backend/profile.
Produces: `update(ctx: AppContext, *, package: Path, backend: IntegrationBackend) -> OperationResult`;
`repair(ctx: AppContext, *, backend: IntegrationBackend) -> OperationResult`;
`uninstall(ctx: AppContext, *, backend: IntegrationBackend, purge_data: bool = False) -> OperationResult`.
Auto-update mevcut sürüm kontrolünü korur ve bu update'e delege edilir;
manifest/version string çoğaltılmaz.

- [ ] **1. Test yaz:** `FoundationOperationsTest.test_operations_preserve_notes_and_disabled_flags`,
  `test_failed_update_restores_app_config_external_records`,
  `test_uninstall_preserves_data_by_default`, `test_owned_record_changed_by_user_is_retained`.
  Fault callback fazları: `backup`, `stage`, `activate`, `config`,
  `integrations`, `health`, `cleanup`; her fazda ayrı subTest.

```python
self.assertEqual(note_hashes(self.vault), before_notes)
self.assertEqual(snapshot(self.vault2), before_vault2)
self.assertEqual(config['integrations'], all_false)
self.assertEqual(snapshot(self.app), before_app)  # başarısız update sonrası
self.assertEqual(backend.read('mcp', self.key), before_external)
self.assertTrue((self.data / 'config.json').exists())  # normal uninstall
self.assertTrue(self.user_changed_hook.exists())
self.assertEqual(note_hashes(self.vault), before_notes)  # purge-data sonrası da
```

- [ ] **2. FAIL doğrula:** `& $py -m unittest -v tests.foundation_operations_test`;
  yeni işlemler yok, import hatası.
- [ ] **3. Uygula:** paket stage doğrulama ve transaction journal; Windows
  açık exe değiştirme işini görev 13 platform aktivasyon kabuğuna devret.
  Her health/alt hata nonzero; eski program/config/external rollback olur.
  Repair yalnız sahipli kaynak/seçilmiş bağlantı ve rebuildable cache;
  template notları overwrite etmez. Uninstall manifest hash/kayıt sahipliği
  doğrular; unmatched dosya korunur. Purge-data açık seçenekle yalnız kanıtlı
  teknik veri, not/root dışına çıkan link yok; DataRoot recursive delete yok.
  Canlı notlara compile/briefing/update-template çağrısı yapılmaz.
- [ ] **4. PASS doğrula:** yeni ve Files'taki dört mevcut modül;
  ayrıca `& $py -m unittest discover -s tests -p '*test*.py'`; OK.
  Faz hata testinde yeni kullanıcı sentinel'i rollback sonrası da kalır.
- [ ] **5. Commit:** görev 10 dosyalarını stage et;
  `git diff --cached --check`; `git commit -m "feat: transact updates repairs and safe uninstall"`.

## For future agent

Bu görevler mevcut özelliklerin dış girişlerini ve kurulum işlemlerini
birleştirir. Setup yeni saf kasa üretir; update/repair/uninstall notları
üretmez. Legacy dönüşüm ve gerçek paket kontrolleri delivery ekindedir.
