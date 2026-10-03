# Modüler temel — görev 11–14

Bu dosya [ana uygulama planının](2026-10-03-modular-foundation.md) sıralı
görev ekidir; görev 1–10 tamamlanınca uygulanır. Global Constraints ve
Review Focus geçerlidir. scope: project; confidence: inferred; supersedes: [].

## Görev 11: Salt okunur legacy envanteri ve önizleme

**Files:** Create: `installation/{legacy,migration}.py`,
`tests/foundation_migration_preview_test.py`; Modify: `cli.py`,
`tests/{global_brand_migration,naming_contract,runtime_layout}_test.py`.

**Interfaces:** Consumes: Roots, ResourceCatalog, manifest/prove_ownership,
IntegrationBackend; ConfigStore.read.
Produces (`legacy.py`):
`LegacyInventory(entries: tuple[MigrationEntry,...], preferences: dict[str,Any], desired: dict[str,bool], conflicts: tuple[str,...])`;
`inventory_legacy(legacy_root: Path, vault: Path, *, roots: Roots, backend: IntegrationBackend) -> LegacyInventory`.
Produces (`migration.py`):
`MigrationEntry(source: Path, target: Path | None, action: str, sha256: str | None, ownership: str)`;
`MigrationPlan(vault_id: str, entries: tuple[MigrationEntry,...], config: dict[str,Any], external: tuple[ExternalChange,...], conflicts: tuple[str,...])`;
`plan_migration(legacy_root: Path, vault: Path, *, roots: Roots, backend: IntegrationBackend, profile: IntegrationProfile) -> MigrationPlan`.
Entry action izinli değerleri: `copy-state`, `preserve-override`, `retain-user`,
`rebuild-cache`, `merge-config`, `remove-owned`, `replace-registration`.
Ownership `manifest-match`, `registry-match`, `user`, `conflict`.
Preview JSON bütün entry source/target/action/hash/ownership alanlarını içerir;
external registry/task değişikliklerini ve desired seçenekleri de gösterir.

- [ ] **1. Test yaz:** `FoundationMigrationPreviewTest.test_dry_run_has_zero_side_effects`,
  `test_flat_nested_and_in_vault_legacy_inventory`,
  `test_config_precedence_and_custom_overrides`,
  `test_conflicting_state_and_reparse_target_block_activation`.
  `seed_legacy(root: Path, *, layout: str) -> None` test yardımcısı bu dosyada
  flat/nested/vault/both varyantlarını üretir; örnek owned manifest ve sha
  fixture'a dahil edilir. Aynı state anahtarının identical ve conflicting
  iki kopyasını ayrı subTest yap. Product basename taşıyan user sentinel
  dosyası manifest dışında olsun; `.py` uzantısı sahiplik sayılmaz.

```python
self.assertEqual(snapshot(self.root), before)
self.assertEqual(backend.applied, [])
self.assertEqual(backend.quiesce_calls, [])
self.assertEqual(plan.config['preferences']['summary_provider'], 'codex')
self.assertEqual(plan.config['preferences']['provider_priority'][0], 'codex')
self.assertEqual(plan.config['integrations'], all_false)
self.assertIn('preserve-override', [entry.action for entry in plan.entries])
self.assertEqual(user_entry.action, 'retain-user')
self.assertTrue(conflicting_plan.conflicts)
self.assertTrue(reparse_escape_plan.conflicts)
```

- [ ] **2. FAIL doğrula:** `& $py -m unittest -v tests.foundation_migration_preview_test`;
  yeni readonly migration import hatası.
- [ ] **3. Inventory/plan uygula:** legacy flat/nested motor, `.beyin` state/
  cache/config, eski `.state`, marker, Inno registry ve external kayıtları
  yalnız oku. Gerçek yeni schema3 config öncelikli; doğrulanmış legacy
  preferences eksikleri tamamlar, defaults son sırada. Config unknown alanları
  ve eski marker kimliği korunacak hedefte yer alır. Kişisel instructions/
  skills paketle byte-eşit değilse UUID overrides hedefini göster. Idempotency
  state rebuild-cache değildir; identical state tek hedef, farklı state
  conflict. Unknown dosya retain-user. Legacy sahiplik yalnız tanınmış
  manifest/hash ya da exact registry kanıtı; isim/uzantı/klasör yetmez.
  Yeni UUID gerekirse sadece plan içinde üret, dry-run marker/config/log/
  backup dizini yaratmaz. Bozuk `RESPECTED_RUNTIME_DIR` açık tanılama;
  normal roots'a dahil edilmez. CLI `migrate` planı yazdırır, conflict varsa
  exit 1; varsayılan hiçbir mutasyon API'si çağırmaz.
- [ ] **4. PASS doğrula:** yeni ve Files'taki mevcut üç test modülü;
  `& $py -m unittest -v tests.foundation_migration_preview_test tests.global_brand_migration_test tests.naming_contract_test tests.runtime_layout_test`;
  OK. Her layout dry-run öncesi/sonrası tam filesystem ve fake registry/task
  byte snapshot eşit. Symlink/junction hedefi dışarıdaysa conflict görünür.
- [ ] **5. Commit:** görev 11 dosyalarını stage et;
  `git diff --cached --check`; `git commit -m "feat: preview legacy migration without mutating user data"`.

## Görev 12: Hash kontrollü geçiş, idempotency ve geri alma

**Files:** Modify: `installation/{migration,transaction}.py`, `cli.py`;
Create: `tests/foundation_migration_apply_test.py`.

**Interfaces:** Consumes: MigrationPlan, Transaction, ConfigStore/Registry,
IntegrationBackend, görev 10 update sağlık/aktivasyon hizmetleri.
Produces: `migration.py: apply_migration(plan: MigrationPlan, *, roots: Roots, package: Path, backend: IntegrationBackend, fault: Callable[[str],None] | None = None) -> OperationResult`.
CLI `--apply` mevcut kurulu yeni dağıtımı `package` olarak geçirir; eski
motor payload'ını yeni paket saymaz. Fazlar sabit: `lock`, `backup`, `stage`,
`activate`, `state`, `config`, `integrations`, `health`, `cleanup`.

- [ ] **1. Test yaz:** `FoundationMigrationApplyTest.test_migration_preserves_notes_preferences_and_overrides`,
  `test_each_phase_failure_rolls_back`, `test_reapply_does_not_duplicate_sessions`,
  `test_changed_or_new_user_file_survives_cleanup`,
  `test_conflict_or_live_writer_prevents_activation`,
  `test_old_uninstaller_is_never_executed`.
  Fazların tamamına ayrı fault enjekte et; işlem lock'undan sonra başka
  süreç yeni `keep.py` yazsın ve bir cleanup adayı motor dosyasını değiştirsin.
  Kullanıcı not fixture'ları daily, knowledge, Companion, proje, Templates,
  `.obsidian` için byte hash ile ölçülür.

```python
self.assertEqual(note_hashes(self.vault), before_notes)
self.assertEqual(config['integrations'], all_false)
self.assertEqual(config['preferences']['summary_provider'], 'codex')
self.assertEqual(override_file.read_bytes(), personalized_bytes)
self.assertEqual(snapshot(self.app), before_app)  # enjekte edilmiş hata sonrası
self.assertEqual(config_file.read_bytes(), before_config)  # rollback sonrası
self.assertTrue(self.new_user_file.exists())
self.assertEqual(self.changed_owned_file.read_bytes(), concurrent_bytes)
self.assertEqual(second_apply.success, True)
self.assertEqual(session_state_after_second_apply, session_state_after_first_apply)
self.assertEqual(old_uninstaller_call_count, 0)
self.assertEqual(activation_calls_for_conflict, 0)
```

- [ ] **2. FAIL doğrula:** `& $py -m unittest -v tests.foundation_migration_apply_test`;
  apply_migration import/imza hatası.
- [ ] **3. Apply uygula:** plan conflict içerirse ilk mutasyondan önce dur.
  Lock+quiesce sonrası source hash ve resolved boundary'leri yeniden kontrol
  et; sonra config/state/external/owned motor backup hash manifesti. Yeni
  paketi stage, validate, activate; eski state UUID hedeflerine transfer ve
  source/target content hash doğrula. Config/marker atomik registration,
  override render önceliği ve yalnız desired external kayıtları. Health
  salt okunur paket/CLI/hook/MCP smoke; not derleme/brifing üretimi çağrılmaz.
  Temizlik sadece unchanged manifest-match dosyalara, dizin sadece boşsa.
  Yeni uninstall registry etkinleşmeden eski unins artefaktına dokunma;
  exact eski registry ownership ve backup şart. Eski uninstaller executable
  hiç çalıştırılmaz. Tüm fazlar journal; unfinished işlem recovery aynı
  expected hash korumasıyla, başka ajanın dosyasını silemez. Yeniden apply
  tamamlanmış entry/UUID/idempotency state'e zarar vermez; cache açıkça rebuild.
- [ ] **4. PASS doğrula:** yeni migration apply/preview ve operation testleri;
  `& $py -m unittest -v tests.foundation_migration_apply_test tests.foundation_migration_preview_test tests.foundation_operations_test`;
  OK. Tam rollback karşılaştırması transaction backup/log/journal'ını hariç
  tutar, eski kullanıcı dosyalarının ve kayıtların byte bütünlüğünü hariç
  tutmaz. Fault sonrası backup manifest ve conflict tanılaması korunur.
- [ ] **5. Commit:** görev 12 dosyalarını stage et;
  `git diff --cached --check`; `git commit -m "feat: migrate legacy installations with ownership and rollback"`.

## Görev 13: Gerçek paketler, eski kaynakların kapanışı ve CI

**Files:** Create/move: ana haritada görev 13 dosyaları;
Modify: `.gitignore`, `pyproject.toml`, `.github/workflows/{ci,release}.yml`,
`README.md`, `docs/{ARCHITECTURE,SPECIFICATION}.md`,
`docs/guides/{BOOTSTRAP,MULTI_AI,SETUP-WINDOWS,SETUP,UNINSTALL,UPDATE}.md`,
`tests/{install_windows_test,windows_launchers_test,briefing_schedule_windows_test,hybrid_wsl_smoke}.ps1`,
`tests/smoke/{platform_smoke.py,windows-native.ps1,linux.sh,macos.sh,wsl.sh}`,
`tests/{hooks_test.sh,upstream_sync_test.sh,run_all.py}`;
Create: `tests/foundation_distribution_test.py`.

**Interfaces:** Consumes: tüm CLI/installation/migration sözleşmeleri.
Produces: `tools/build_installer.py: build(*, platform: str, output: Path) -> Path`;
`tools/verify_distribution.py: verify(distribution: Path, *, platform: str) -> int`;
komutlar `python tools/build_installer.py --platform windows --output dist`,
`python tools/verify_distribution.py --distribution <dist-path> --platform windows`.
macOS/linux ilgili platform değerleriyle native CI üzerinde üretilir.
Windows shell Inno + activate-on-exit, ortak setup/update/repair/uninstall
hizmetini kullanır; sahipli payload için silme kararı hizmet manifestinden gelir.

- [ ] **1. Test yaz:** `FoundationDistributionTest.test_frozen_runs_without_checkout_or_python`,
  `test_readonly_app_root_and_single_engine`,
  `test_inno_does_not_reuse_old_vault_as_app_dir`,
  `test_executable_in_use_update_and_rollback`,
  `test_legacy_wrappers_forward_exit_code`.
  Geçici Windows install root, PATH'te Python yok; başka CWD/emoji kasa.
  AppRoot'a yazmayı native ACL ile engelle, normal çalışmada logs/state/cache
  DataRoot'ta oluşsun. Layout kontrolü sadece dosya ismiyle engine saymaz;
  bundle manifest ve import kaynak kökü tek olsun.

```python
self.assertEqual(frozen_version.returncode, 0)
self.assertEqual(frozen_version.stdout.strip(), '0.0.1')
self.assertFalse((installed_app / 'runtime').exists())
self.assertFalse((installed_data / 'scripts').exists())
self.assertTrue((installed_app / 'app/respectedbrain/resources/defaults.json').exists())
self.assertTrue((installed_app / 'uninstall/unins000.exe').exists())
self.assertEqual(inno_registered_app_root, installed_app)
self.assertEqual(note_hashes(self.vault), before_notes)
self.assertEqual(legacy_shim_result.returncode, delegated_result.returncode)
self.assertEqual(snapshot(installed_app), before_app)  # failed activation rollback
```

- [ ] **2. FAIL doğrula:** `& $py -m unittest -v tests.foundation_distribution_test`;
  yeni dist veya yeni Inno yerleşimi yok, test hata verir. Build gerektiren
  testler artifact yoksa sessiz skip yapmaz; test runner build'i önce çağırır.
- [ ] **3. Paket/CI uygula:** PyInstaller onedir `--contents-directory app`,
  kaynaklar manifestten tek kopya. Inno AppId korunur, lowest privileges,
  `UsePreviousAppDir=no`, uninstall directory AppRoot/uninstall; vault ayrı
  ayar. Geniş `[UninstallDelete]` kalkar; standart Inno payload temizliği de
  manifest dışı dosyayı silmemeli (payload `uninsneveruninstall` + doğrulanmış
  deletion list). Windows aktivasyon/kaldırma açık exe'yi yerinde değiştirmeyi
  varsaymaz; işlem bitiminde OS temp'teki doğrulanmış helper/Inno callback
  staged işlemi journal'a göre sürdürür. DataRoot'ta executable helper tutulmaz.
  Son health failure restore ve native task/registry rollback testleri şart.
  macOS `.app/Contents/MacOS` launcher ve Linux AppRoot binary + `.local/bin`
  launcher aynı paket; native test geçmeden release verified sayılmaz.
  Ortak setup hizmetini çağıran thin platform launchers dışında duplicate
  installer/motor kaynaklarını kaldır. Bir geçiş sürümü old CLI path shim
  sadece yeni CLI'a import/subprocess delegasyonu ve aynı exit code; frozen
  payload'da eski runtime ağacı yok. Old template/skills/default kaynak
  kopyaları kapanır; tools/upstream source path'leri yeni kaynakları kullanır.
  CI editable tests + izolasyonlu wheel + frozen smoke/native installation;
  render check artık kaynakların geçerliliğini/reproducibility'sini sınar,
  kullanıcı HOME'a render etmez. Workflow clean-tree kontrolü korunur.
- [ ] **4. Belgeleri güncelle:** mevcut rehberlerin güncel hali okunarak
  path/komut/default kurulum ve güvenli upgrade anlatımı değiştirilir.
  Kullanıcıya üç konum örneği ve SSS; runtime/template/data farkı gösterilir.
  Aktif mimari SSOT ana spec bağlantısıdır; tarihli eski davranış önceki
  karar olarak tutulur, güncel hedefle çelişen talimat olarak bırakılmaz.
  25 KB aşan not içerik silmeden alt dosyalara bölünür.
- [ ] **5. PASS doğrula:** `& $py -m build --wheel`,
  `& $py tools/build_installer.py --platform windows --output dist`,
  `& $py tools/verify_distribution.py --distribution dist/RespectedBrain --platform windows`,
  `& $py -m unittest discover -s tests -p '*test*.py'`,
  `& $pwsh -NoProfile -File tests/install_windows_test.ps1`,
  `& $pwsh -NoProfile -File tests/briefing_schedule_windows_test.ps1`,
  `& $pwsh -NoProfile -File tests/smoke/windows-native.ps1`.
  OK/exit 0. Windows Inno silent install/update/uninstall registry ve
  kullanımda exe senaryoları geçici kasa ile gerçek process üzerinde koşar;
  GUI wizard aynı common service çağrısının native smoke'u raporlanır.
  Linux/macOS matrix kaynak/wheel/frozen/POSIX hook testleri native koşar.
  Gerçek WSL smoke WSL varsa; yoksa gerekçeli skip. Bütün atlamalar açık rapor.
- [ ] **6. Commit:** görev 13 kaynak/docs/tests/workflow ve silinen eski
  kaynak dosyalarını açıkça stage et; `setup.exe` tracked kaydı kaldırılır,
  build çıktıları commit edilmez. `git diff --cached --check`;
  `git commit -m "build: ship one self-contained app and retire duplicate runtime layout"`.

## Görev 14: Gerçek bilgisayarda denetlenen devreye alma

**Files:** Ürün kodu değişmez. İşlem backup/journal dosyaları DataRoot'ta,
raporun özeti mevcut proje notunun ana spec/kanıt bağlantılarında.

**Interfaces:** Consumes: verified frozen launcher, plan_migration/apply_migration,
yerel kullanıcının gerçek yolları ve mevcut desired seçenekleri.
Produces: gerçek AppRoot/DataRoot/VaultRoot son yerleşim kanıtı veya
çözümlenmemiş conflict raporu; başarı iddiası yalnız native kontroller sonrası.

- [ ] **1. Canlı readonly envanteri çıkar:** eski AppData, RespectedOS marker/
  `.beyin`, uninstall registry, provider/MCP/schedule/shortcut kayıtlarını
  yeni launcher ile dry-run yap. Her source→target/retain/remove-owned
  adayını ve preferences/desired flags'i kullanıcıya somut göster.
  `respectedbrain.exe migrate --legacy-root <gerçek-legacy-root> --vault <gerçek-vault>`
  filesystem/registry/tasks byte snapshot'larını değiştirmemeli.
- [ ] **2. Devreye alma kapısını değerlendir:** kullanıcıya backup hedefi,
  korunacak notlar, kaldırılacak yalnız sahipli artıklardan oluşan gerçek
  önizleme ve rollback komutunu sun. Somut canlı değişiklik için mevcut
  yetkiyi değerlendir; yeni onay gerekiyorsa bu son adımda iste. Conflict,
  başarısız test veya çözümlenmemiş sahiplik varken apply yapma.
- [ ] **3. Onaylı geçişi uygula:** backup manifest doğrula, active writers
  quiesce/lock; verified yeni Windows kurucu/AppRoot kurulumu ve ortak
  `migrate ... --apply`. Geniş temizlik yapan eski uninstaller çalışmaz.
  Paket kurucusunun otomatik migration yapması halinde ikinci kez farklı
  bir bağımsız migration çalıştırma; aynı transaction/idempotency geçerlidir.
- [ ] **4. Son durumu doğrula:** stable launcher version/vault list, seçili
  provider hook/MCP test session, panel ve yeni teknik state/cache yolları;
  disabled integration'lar hâlâ kapalı. Not hash'leri deployment öncesiyle
  eşit; explicit user test oturumunun beklenen yeni günlük girişi ayrıca
  ayrılır. AppRoot tek paket, DataRoot config/state/cache/log/backup,
  RespectedOS mevcut konumda. Hata varsa journal rollback ve aynı hash test.
- [ ] **5. Devir:** geçen komutlar, atlanan platformlar ve backup transaction
  kimliğini bildir; mevcut proje ana kaydına kanıt bağlantısı, Last-Session/
  Threads/Journal protokolüne sonuç. Aktif hedef ağacını vault'ta kopyalama.

## For future agent

Dry-run gerçekten sıfır yan etkilidir; apply ownership/hash/lock/journal
üzerinden yürür. Eski kaldırıcıyı çalıştırma ve bilinmeyen dosyayı silme.
Canlı geçiş, sandbox ve native paket testlerinden sonra somut önizlemeyle
yapılır; conflict veya arıza varsa işi başarı olarak raporlama.
