# 📋 Güvenlik Sertleştirmesi Uygulama Kaydı — 2026-10-07

scope: project; confidence: verified; supersedes: ["2026-10-06 uygulama kaydındaki custom child çalıştırma, bypass flag ve signer-workflow iddiaları"]

## 1. Kapsam

Bu kayıt üçüncü bağımsız incelemedeki P1/P2 bulgularının ve aynı güvenlik alanına
sızan eski iddiaların uygulama/kanıt kapanışını tutar. Canlı program, canlı kullanıcı
verisi, kişisel RespectedOS kasası, canlı provider ayarları ve Git publication hedefi
kullanılmadı. Commit/push/tag/release/reset/stash/clean ve CI bekleme çalıştırılmadı.

## 2. Uygulanan kök düzeltmeler

### A. Provider containment ve fail-closed custom
- `providers/runner.py`: `_run_process_tree` Windows Job Object ve POSIX process
  group tabanlı ağaç sonlandırma uygular; timeout/nonzero/partial-output sözleşmesi
  görünür kalır.
- `BEYIN_LLM_COMMAND` mevcutken `run_model` child oluşturmadan
  `custom-isolation-required` döndürür. `_custom_argv` yalnız parsing testlerinde
  kullanılır.
- Provider mock seam'leri gerçek sınır olan `_run_process_tree` düzeyine taşındı.
- `tests/security_hardening_third_fix_test.py` dış iç/dış yazma child'larının hiç
  başlamadığını, `tests/provider_permissions_test.py` bypass flag yokluğunu,
  `tests/adversarial_quality_test.py` quoting ve timeout/çıktı ağaç davranışını,
  `tests/windows_native_test.py` gerçek fixture CLI sürecini doğrular.

### B. Snapshot tree ve ref bağlama
- `maintenance/backup/publish_git_snapshot.py`: copied user index / HEAD tree /
  empty tree başlangıcı, iki aşamalı index+immutable tree sır taraması,
  `commit-tree <tree_sha>` ve uzak ref eşitlik doğrulaması eklendi.
- `tests/snapshot_immutable_publish_test.py` gerçek geçici Git repo ve bare remote
  kullanır; scan sonrası isolated-index injection, staged secret, clean-filter
  injection ve tracked/ignored note korunumu kalıcıdır.
- `tests/secret_scanner_test.py` forbidden filename/content pattern, okuma hatası ve
  symlink kaçış fail-closed davranışlarını destekler.

### C. Strict release provenance zinciri
- `installation/provenance.py`: JSON ve JSONL/concatenate edilmiş DSSE bundle
  ayrıştırma, exactly-one envelope, manifest SHA-256 ↔ SLSA subject digest, repo,
  workflow ve exact release ref kontrolü vardır.
- `installation/payload.py`: normal consumer varsayılanı `require_provenance=True`;
  yalnız çağrı kodunun açıkça verdiği test politikası fixture olarak kullanılabilir.
- `tests/foundation_install_support.py` scoped synthetic attestation ve fake `gh`
  fixture verifier üretir; global unsigned env yoktur.
- `.github/workflows/release.yml`: `gh 2.102.0` checksum pin, manifest attestation,
  embed/download, strict consumer verify ve outer asset verify sırasını zorlar.
- `tests/release_provenance_test.py` hash/ref/foreign origin/unsigned/missing host
  verifier/JSONL vakalarını, `tests/release_workflow_security_test.py` release sırasını,
  `tests/provenance_lifecycle_transport_test.py` setup/update/repair/deferred attestation
  kalıcılığını doğrular.
- `tests/security_hardening_third_fix_test.py` gerçek `gh 2.102.0` yardımındaki
  bayrak setini sabitler: `--cert-identity`, `--cert-oidc-issuer`, `--source-ref`,
  `--predicate-type`, `--deny-self-hosted-runners`, `--limit 1`; `--signer-workflow`
  ve yanlış `--cert-identity-issuer` yoktur.

### D. HTTP deadline ve resolver sınırları
- `maintenance/ingestion/defuddle.py`: status/header, chunk framing ve body okumaları
  `_DeadlineReader` üzerinde tek mutlak deadline paylaşır; deadline sonrası gecikmiş
  başarı reddedilir.
- Resolver en fazla iki daemon worker kullanır ve process shutdown'ta bekletmez.
- `tests/dns_pinning_transport_test.py` socket-pair/header/chunk ulaşımını,
  `tests/security_hardening_third_fix_test.py` EOF sonrası deadline, bounded worker ve
  process shutdown davranışını doğrular.

## 3. Yerel doğrulama

| Kanıt | Sonuç |
| --- | --- |
| Odak third-fix paketi | VERIFIED: 22 test, 22 pass, 0 failure/error |
| Frozen package/source compare | VERIFIED: 5 kritik modül semantic_code_equal=true |
| Distribution integrity smoke | VERIFIED: native frozen version/registry/maps/search/hook/MCP OK |
| Strict frozen lifecycle | VERIFIED: 23/23 kontrol; fixture policy yalnız test scoped verifier |
| Native install/update tests | VERIFIED: 3 test, 2 pass; 1 Inno compiler unavailable skip |
| Inno shared-service tests | VERIFIED: 3/3 pass |
| Immutable snapshot tests | VERIFIED: gerçek Git fixture ve bare remote ile geçti |

## 4. NOT VERIFIED dış sınırlar

- Gerçek GitHub Actions OIDC + Sigstore/GitHub attestation imzası.
- Authenticode kod imzalama sertifikası ve imzalı outer installer.
- Gerçek çok kullanıcılı/uzak GitHub publication ve auth hataları.
- Inno compiler erişimi; bu host'ta LocalAppData adayı `PermissionError` veriyor ve
  Program Files adayı bulunmuyor. Gerçek Inno installer üretimi ve kurulumu
  doğrulanmadı; ilgili test kontrollü skip'tir.
- PyInstaller build logu `tkinter installation is broken. It will be excluded`
  bildiriyor; frozen GUI çalıştırma doğrulanmadı.
