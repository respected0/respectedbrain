#!/bin/bash
# Explicit-context package hook regressions; fixtures are temporary and providers are mocked.
set -eu
TEST_ROOT=$(CDPATH= cd -- "${BASH_SOURCE[0]%/*}/.." 2>/dev/null && pwd)
cd "$TEST_ROOT"
PYTHON_COMMAND=${RESPECTED_TEST_PYTHON:-python3}
export PYTHONIOENCODING=utf-8
"$PYTHON_COMMAND" -m unittest -v \
 tests.foundation_integrations_test.FoundationIntegrationsTest.test_hook_protocol_uses_selected_uuid_state_and_stable_session_id \
 tests.multiai_test.MultiAITest.test_bridge_normalizes_provider_inputs_and_outputs \
 tests.multiai_test.MultiAITest.test_antigravity_normalize_resolves_ide_then_cli_transcript \
 tests.multiai_test.MultiAITest.test_antigravity_normalize_uses_stable_transcript_session_when_invocation_ids_change \
 tests.multiai_test.MultiAITest.test_antigravity_transcript_discovery_is_safe_and_explicit_wins \
 tests.multiai_test.MultiAITest.test_codex_transcript_discovery_and_safety \
 tests.multiai_test.MultiAITest.test_bridge_dispatches_to_shared_lifecycle_without_shell_hooks \
 tests.multiai_test.MultiAITest.test_global_bridge_distinguishes_windows_vault_and_external_paths
