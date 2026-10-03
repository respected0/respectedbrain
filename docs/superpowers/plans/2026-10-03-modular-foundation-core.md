# Modüler temel — görev 1–5

Bu dosya [ana uygulama planının](2026-10-03-modular-foundation.md) sıralı
görev ekidir. Global Constraints, Review Focus ve çalışma disiplini aynen
geçerlidir. scope: project; confidence: inferred; supersedes: [].

## Görev 1: Kurulabilir tek paket ve immutable kaynaklar

**Files:** Create: ana dosya haritasındaki görev 1 dosyaları; Modify:
`.gitignore`; Test: `tests/package_contract_test.py`.
Kaynaklar ilk aşamada güncel runtime/template'den alınır; eski çalışır
girişleri bozmamak için kaynak kopyalarının kesin kaldırılması görev 13'tedir.

**Interfaces:** Consumes: mevcut template/config/instructions/skills/adapters/web.
Produces: `cli.main(argv: Sequence[str] | None = None) -> int`;
`ResourceCatalog.read_text(relative: str) -> str`,
`ResourceCatalog.iter_files(relative: str) -> tuple[str,...]`,
`ResourceCatalog.materialize(relative: str) -> ContextManager[Path]`
(`core/resources.py`); `__version__` yalnız `importlib.metadata.version("respectedbrain")`.

- [ ] **1. Test yaz:** `PackageContractTest.test_resources_and_import_are_independent_of_checkout`.
  Ayrı venv'e wheel kur, repo dışından import et; aşağıdaki kontrolleri yap.
  Import denetimi subprocess/mkdir girişimlerini ve test kullanıcısı config
  dosyasının açılmasını hata sayar. Paket importları bytecode yazmasın diye
  çocuk süreçte `PYTHONDONTWRITEBYTECODE=1` kullan.

```python
self.assertEqual(metadata.version('respectedbrain'), '0.0.1')
self.assertIn('🔮 850-Companion/Core.md', resources.iter_files('vault-template'))
self.assertIn('SKILL.md', resources.iter_files('skills/beyin-doktor'))
self.assertEqual(json.loads(resources.read_text('defaults.json'))['summary_provider'], 'auto')
self.assertEqual(snapshot(self.user_root), before)
self.assertEqual(import_audit.user_config_reads, [])
self.assertEqual(import_audit.process_calls, [])
```

- [ ] **2. FAIL doğrula:** `& $py -m unittest -v tests.package_contract_test`;
  paket/resources henüz yokken import/build hatası beklenir.
- [ ] **3. Paketi uygula:** setuptools src discovery, paket data hiddenfiles
  dahil açık manifest; `version = "0.0.1"`, `requires-python = ">=3.10"`, CLI entry point
  `respectedbrain = "respectedbrain.cli:main"`. `__main__` aynı main'i çağırır.
  ResourceCatalog `importlib.resources.files/as_file` kullanır; dizin
  materialize işlemi Python 3.10'da Traversable dosyalarını context-managed
  temp dizine kopyalar, directory-as_file desteğini varsaymaz. Mutlak yol,
  `..` ve dışarı çıkan kaynak adını reddeder. İlk CLI sadece `--help/--version`
  sunar. Defaults'taki legacy `platform/python_command` yalnız migration
  için okunabilir; yeni Python seçimini bunlar yönetmez. Template'teki eski
  `.respectedbrain-version` ürün sürüm kopyası yeni template'e alınmaz;
  metadata tek kaynak kalır. Generated adapter skill kopyaları kaynak
  envanterinde ayrı işaretlenir ve ikinci resource skill ağacı yapılmaz.
  Test yardımcılarını
  ana planın imzalarıyla yaz; yeni runtime kaynaklarını eski state'den ayır.
- [ ] **4. PASS doğrula:** önce `& $py -m pip install -e '.[dev]'`, sonra
  `& $py -m build --wheel` ve aynı unittest komutu; build başarılı/test OK.
  Ayrı venv'e `dist/*.whl` kurma testi checkout'u PYTHONPATH'e eklemez.
- [ ] **5. Commit:** yalnız `pyproject.toml`, `.gitignore`, `src/respectedbrain`,
  iki yeni test/yardımcı dosyasını stage et; `git diff --cached --check`;
  `git commit -m "build: introduce installable respectedbrain package"`.

## Görev 2: Saf platform yolları ve tek bağlam

**Files:** Create: `core/{paths,platform,context,errors}.py`,
`tests/foundation_paths_test.py`; Modify: görev 1 resource güvenlik testi.

**Interfaces:** Consumes: ResourceCatalog. Produces:
`Roots(app_root: Path, data_root: Path, default_vault: Path)`;
`resolve_roots(*, platform: str, home: Path, env: Mapping[str,str], known_folder: Callable[[str],Path]) -> Roots`;
`AppPaths(app_root, data_root, vault_root: Path, vault_id: str)` frozen dataclass,
özellikleri `state_dir`, `cache_dir`, `log_dir`, `backup_dir`, `overrides_dir: Path`;
`AppContext(paths: AppPaths, config: dict[str,Any], resources: ResourceCatalog)`;
`FoundationError`, alt sınıflar `SelectionError`, `IdentityConflict`,
`StateConflict`, `OwnershipConflict`, `BusyError` (`core/errors.py`).
`known_folder` native Windows `SHGetKnownFolderPath` üzerinden `LocalAppData`,
`Documents` değerlerini bulur; platform testleri callback enjekte eder.

- [ ] **1. Test yaz:** `FoundationPathsTest.test_redirected_documents_and_separate_roots`,
  `test_other_platform_roots`, `test_overrides_do_not_use_legacy_runtime_dir`.
  Home ve known folder farklı dizinler olsun; hiçbir çağrı mkdir yapmasın.

```python
self.assertEqual(roots.app_root, self.local / 'Programs/RespectedBrain')
self.assertEqual(roots.data_root, self.local / 'RespectedBrain')
self.assertEqual(roots.default_vault, self.redirected_docs / 'RespectedOS')
self.assertEqual(paths.state_dir, paths.data_root / 'vaults' / self.uuid / 'state')
self.assertEqual(paths.cache_dir, paths.data_root / 'vaults' / self.uuid / 'cache')
self.assertEqual(paths.log_dir, paths.data_root / 'logs')
self.assertEqual(paths.backup_dir, paths.data_root / 'backups')
self.assertEqual(snapshot(self.root), before)
self.assertEqual(linux.data_root, self.xdg / 'respectedbrain')
self.assertEqual(mac.data_root, self.home / 'Library/Application Support/RespectedBrain')
```

- [ ] **2. FAIL doğrula:** `& $py -m unittest -v tests.foundation_paths_test`;
  henüz tanımlanmamış paths/platform import hatası.
- [ ] **3. İmzaları uygula:** saf resolver ENV'nin açık override'larını kabul
  eder; yoksa OS varsayılanları. `RESPECTED_RUNTIME_DIR` yeni roots'u
  değiştirmez. App/data/vault kesişmesi, relative override ve geçersiz UUID
  SelectionError; dizin oluşturmak burada yasaktır. Linux Documents yoksa
  home, macOS Documents yoksa home fallback'ini test et. Runtime'da gerçek
  executable konumu frozen dağıtım tarafından bootstrap'a açık aktarılır.
- [ ] **4. PASS doğrula:** aynı unittest komutu ve
  `& $py -m unittest -v tests.package_contract_test`; OK.
- [ ] **5. Commit:** görev 2 kaynak/test dosyalarını açıkça stage et;
  `git diff --cached --check`; `git commit -m "refactor: centralize application data and vault paths"`.

## Görev 3: Config, kalıcı UUID ve kasa seçimi

**Files:** Create: `core/config.py`, `vault/registry.py`,
`tests/vault_registry_test.py`; Modify: `core/context.py`.

**Interfaces:** Consumes: Roots/AppPaths/errors.
Produces: `ConfigStore(data_root: Path)`, `read() -> dict[str,Any]`,
`update(mutator: Callable[[dict[str,Any]],None]) -> dict[str,Any]`;
`VaultRegistry(store: ConfigStore)`,
`register(path: Path, *, new_identity: bool = False) -> str`,
`list() -> dict[str,dict[str,Any]]`, `discover(start: Path) -> Path | None`,
`select(*, vault: Path | None, vault_id: str | None, env: Mapping[str,str]) -> tuple[str,Path]`;
`build_context(roots: Roots, store: ConfigStore, *, vault: Path | None, vault_id: str | None, env: Mapping[str,str]) -> AppContext`.

- [ ] **1. Test yaz:** `VaultRegistryTest.test_selector_priority_and_invalid_explicit_path`,
  `test_move_and_copy_uuid`, `test_concurrent_config_edits_survive`.
  Yeni UUID gerçek uuid4; sabit fixture UUID
  `11111111-1111-4111-8111-111111111111`. Config/marker unknown alanı `custom: 7`.
  Eşzamanlı test iki gerçek child process'i bariyerle aynı anda update ettirsin.

```python
self.assertEqual(registry.select(vault=self.vault2, vault_id=None, env=env)[1], self.vault2)
with self.assertRaises(SelectionError):
    registry.select(vault=self.missing, vault_id=None, env=env)
with self.assertRaises(SelectionError):
    registry.select(vault=self.vault1, vault_id=self.uuid, env={})
self.assertEqual(registry.register(self.moved_vault), self.uuid)
with self.assertRaises(IdentityConflict):
    registry.register(self.copied_vault)
self.assertNotEqual(registry.register(self.copied_vault, new_identity=True), self.uuid)
self.assertEqual(store.read()['preferences'], {'theme': 'dark', 'summary_provider': 'codex'})
self.assertEqual(store.read()['custom'], 7)
self.assertEqual(json.loads(marker.read_text())['schema_version'], 3)
self.assertNotIn('runtime_path', json.loads(marker.read_text()))
```

- [ ] **2. FAIL doğrula:** `& $py -m unittest -v tests.vault_registry_test`;
  registry/config import hatası.
- [ ] **3. İmzaları uygula:** explicit select, sonra ENV, sonra active UUID;
  bilinmeyen/eksik marker ve kayıt hata, CWD otomatik fallback yok. Discover
  salt okunur ancestor marker arar. Register UUID'yi korur; eski kayıtlı yol
  artık yoksa taşınmış kasanın yolunu günceller, iki canlı path aynı UUID ise
  hata. `new_identity=True` yalnız açık kopya kaydıdır. Marker dönüşümünden
  önce backup al, bilinen machine-path alanlarını legacy metadata altında
  sakla; aktif marker'a mutlak program yolu koyma. Unknown kimlik alanlarını
  koru. ConfigStore read hiçbir şey yaratmaz; update cross-process lock
  altında son hali okur, validate ve temporary+os.replace/fsync ile yazar.
- [ ] **4. PASS doğrula:** aynı unittest komutu; ayrıca yanlış CWD'den ENV
  seçiminin aktif kasayı geçmesini ve env açık geçersizken hata olmasını
  sınayan iki testi çalıştır; OK, ikinci kasanın snapshot'ı değişmez.
- [ ] **5. Commit:** görev 3 dosyalarını stage et;
  `git diff --cached --check`; `git commit -m "feat: register stable vault identities and locked config"`.

## Görev 4: Sağlayıcı ve hafıza motorunu bağlama taşımak

**Files:** Create/move: ana haritada görev 4 modülleri;
Modify: `tests/{lifecycle,turn_log_pipeline,event_log,output_normalization,
knowledge_domain,graph_and_session,orchestration_recovery,zero_trust_security,
boundary_regression,regression_matrix,runtime_layout}_test.py` import/fixture'ları;
Test: `tests/foundation_memory_test.py`. Taşınan kaynakların spec §5 eşleşmeleri
bu görevde yeni kod veya ince delegasyon olur; iki runtime_hub mantığı kalmaz.

**Interfaces:** Consumes: AppContext, ConfigStore.
Produces: `core/context.py` içinde `ModelResult(text: str | None, provider: str | None, error: str | None)`
ve `ModelService` Protocol:
`run(prompt: str, *, cwd: Path, mode: Literal['text','workspace'], timeout: float) -> ModelResult`;
`providers/runner.py: ModelRunner(ctx: AppContext)` bu protokolü uygular.
`memory/lifecycle.py: handle_event(ctx: AppContext, *, event: str, session_id: str, transcript: Path | None, payload: dict[str,Any], now: datetime) -> str`;
`memory/flush.py: flush(ctx: AppContext, *, session_id: str, transcript: Path, model: ModelService, now: datetime) -> int`;
`memory/compile.py: compile_memory(ctx: AppContext, *, model: ModelService, now: datetime) -> int`.
İç saf parsing/graph/normalization imzaları davranışı değiştirmeden korunur.

- [ ] **1. Test yaz:** `FoundationMemoryTest.test_two_vaults_share_package_not_session_state`,
  `test_compile_claim_and_flush_idempotency_survive_restart`,
  `test_provider_preferences_come_from_user_config`.
  `FakeModel` bu test dosyasında ModelService imzasını uygular; `calls: int`
  her run'da artar, `response: str` mevcut geçerli beş bölümlü summary
  fixture'ından gelir, sonuç `ModelResult(response, 'codex', None)` olur.
  İki kasada aynı session adı, sabit fake model çıktısı, aynı transcript
  tekrar işlensin. Test salt okunur app fixture'ı kullansın.

```python
self.assertEqual(flush(ctx1, session_id='same', transcript=t1, model=fake, now=now), 0)
self.assertEqual(flush(ctx1, session_id='same', transcript=t1, model=fake, now=now), 0)
self.assertEqual(daily1.read_text().count('RESPECTED-SESSION:'), 2)  # BEGIN + END
self.assertEqual(snapshot(ctx2.paths.state_dir), before2)
self.assertEqual(snapshot(ctx1.paths.app_root), before_app)
self.assertFalse((ctx1.paths.vault_root / '.beyin').exists())
self.assertEqual(runner_preferences['summary_provider'], 'codex')
self.assertEqual(runner_preferences['provider_priority'][0], 'codex')
```

- [ ] **2. FAIL doğrula:** `& $py -m unittest -v tests.foundation_memory_test`;
  yeni hizmet import/imza hatası.
- [ ] **3. Taşı ve bağla:** algoritmaları güncel dosyadan al; globals yerine ctx.
  State/locks/trigger claims → paths.state_dir; türetilmiş graf/cache → cache_dir;
  model stage → teknik temp/cache alanı. Compile subprocess `.py` aramasını
  ortak hizmet çağrısına dönüştür; uzun iş için gerekiyorsa tek launcher'a
  `compile --vault-id` delege et. Provider preferences sadece ctx config;
  fallback/timeout/output parsing mevcut davranışını korur. Import sırasında
  stream reconfigure ve config okuma kalkar. Session/event anahtarları değişmez.
- [ ] **4. PASS doğrula:** yeni test ve Files'taki mevcut test modüllerini
  `& $py -m unittest -v tests.foundation_memory_test tests.lifecycle_test tests.turn_log_pipeline_test tests.event_log_test tests.output_normalization_test tests.knowledge_domain_test tests.graph_and_session_test tests.orchestration_recovery_test tests.zero_trust_security_test tests.boundary_regression_test tests.regression_matrix_test tests.runtime_layout_test`
  ile çalıştır; OK. Eski import/state yol beklentisi yeni ctx'ye çevrilir.
- [ ] **5. Commit:** taşınan görev 4 kaynaklarını, eski yolların kaldırma/ince
  yönlendirmelerini ve Files'taki testleri açıkça stage et;
  `git diff --cached --check`; `git commit -m "refactor: move memory jobs to explicit application context"`.

## Görev 5: Arama, brifing ve kasa haritaları

**Files:** Move: `runtime/scripts/arama.py` → `search/engine.py`,
`runtime/morning_briefing.py` → `briefing/service.py`, `runtime/map_builder.py`
→ `vault/maps.py`; Modify: `tests/{maps,morning_briefing,mcp_and_features}_test.py`;
Create: `tests/foundation_features_test.py`.

**Interfaces:** Consumes: AppContext, ModelService, compile_memory.
Produces: `search/engine.py: SearchEngine(ctx: AppContext)` (mevcut query sonuç
şeması korunur); `briefing/service.py: run_if_due(ctx: AppContext, *, model: ModelService, now: datetime) -> int`;
`vault/maps.py: rebuild_maps(ctx: AppContext) -> None`.

- [ ] **1. Test yaz:** `FoundationFeaturesTest.test_index_and_briefing_use_same_uuid_data`,
  `test_briefing_does_not_create_legacy_engine`.
  Arama cache, brifing state, compile claim'in tümü aynı ctx ile üretilecek;
  aynı gün tekrar brifing modelini çağırmayacak.

```python
self.assertTrue(any(ctx.paths.cache_dir.rglob('*.db')))
self.assertTrue(any(ctx.paths.state_dir.iterdir()))
self.assertFalse((self.vault / '.beyin').exists())
self.assertFalse(any(self.vault.rglob('*.db')))
self.assertEqual(fake.calls, calls_after_first_briefing)
self.assertEqual(snapshot(self.app), before_app)
self.assertEqual(snapshot(self.vault2), before_vault2)
```

- [ ] **2. FAIL doğrula:** `& $py -m unittest -v tests.foundation_features_test`;
  yeni service/context import veya eski DB konumu assertion hatası.
- [ ] **3. Taşı:** search DB'nin mevcut filename/şeması korunur, kökü cache_dir;
  brifing due/health/lock state_dir, çıktı mevcut Briefings/Dashboard'a;
  haritalar mevcut vault notlarını üretir. Mevcut not üretme işlevleri bu
  görevde çalıştırılınca ilgili not değişebilir; install/update/migration
  kendi başına bu işlevleri kullanıcı notlarına karşı çağırmaz.
- [ ] **4. PASS doğrula:** `& $py -m unittest -v tests.foundation_features_test tests.maps_test tests.morning_briefing_test tests.mcp_and_features_test`;
  OK, uygulama kökü hash'leri sabit.
- [ ] **5. Commit:** görev 5 dosyalarını ve eski giriş delegasyonlarını stage et;
  `git diff --cached --check`; `git commit -m "refactor: isolate search and briefing data per vault"`.

## For future agent

İlk beş görev paket, yol, kimlik ve mevcut hafıza işlevlerini kurar.
Kaynak davranışını yeni ürün özelliği eklemeden koru; import-time kullanıcı
verisi erişimini kaldır. Sonraki görevler services ekindedir.
