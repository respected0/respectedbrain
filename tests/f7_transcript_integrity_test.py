"""F7 ownership, provenance and immutable transcript regression tests."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock

from respectedbrain.memory import flush as F
from respectedbrain.core.context import ModelResult
from tests.foundation_support import make_context

SID = '12345678-1234-4123-8123-123456789abc'
OTHER = '23456789-2345-4234-8234-23456789abcd'
NOW = dt.datetime(2026, 10, 8, 12, 0, tzinfo=dt.timezone.utc)
SUMMARY = '\n'.join('## ' + s + '\nORIGINAL' for s in F.EXPECTED_SECTIONS)

class Model:
    def __init__(self, marker='ORIGINAL'):
        self.calls = 0
        self.marker = marker
    def run(self, prompt, **kwargs):
        self.calls += 1
        return ModelResult(SUMMARY.replace('ORIGINAL', self.marker), 'codex', None)

class F7TranscriptIntegrityTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='f7-independent-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.ctx = make_context(self.root, self.root / 'vault-a')
        self.vault = self.ctx.paths.vault_root
        self.state = self.ctx.paths.state_dir
        self.state.mkdir(parents=True)
        self.home = self.root / 'home'
        self.sessions = self.home / '.codex/sessions'
        self.sessions.mkdir(parents=True)
        self.daily = self.vault / 'daily/2026-10-08.md'
        self.env = mock.patch.dict(os.environ, {'BEYIN_PROVIDER': 'codex'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.unrelated = [self.root / "human.txt", self.vault / "knowledge/human.md"]
        for path in self.unrelated:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"UNRELATED HUMAN BYTES\r\n")
        self.addCleanup(lambda: [self.assertEqual(path.read_bytes(), b"UNRELATED HUMAN BYTES\r\n") for path in self.unrelated])
    def write(self, path, payload=None, marker='USER', records=None):
        data = records if records is not None else ([] if payload is None else [{'type': 'session_meta', 'payload': payload}])
        data = data + [{'role': 'user', 'content': marker}]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('\n'.join(json.dumps(r) for r in data) + '\n', encoding='utf-8')
        os.utime(path, (NOW.timestamp()-60, NOW.timestamp()-60))
        return path
    def transcript(self, payload=None):
        return self.write(self.sessions / f'rollout-{SID}.jsonl', payload)
    def run_flush(self, path, model=None, when=NOW):
        return F.flush_transcript(self.ctx, session_id=SID, transcript=path, model=model or Model(), now=when)
    def catch(self, model=None):
        return F.catch_up_unflushed_sessions(self.ctx, model=model or Model(), now=NOW, home=self.home)
    def hook(self):
        return F.record_hook_workspace(self.state, self.ctx.paths.vault_id, SID, 'codex', {'cwd': str(self.vault)})
    def test_direct_foreign_metadata_rejected(self):
        foreign = make_context(self.root, self.root / 'vault-b')
        p = self.transcript({'id': SID, 'cwd': str(foreign.paths.vault_root)})
        model = Model('FOREIGN')
        status = self.run_flush(p, model)
        self.assertEqual(status, 1)
        self.assertFalse(self.daily.exists())
    def test_cli_hook_input_foreign_metadata_rejected(self):
        from respectedbrain import cli
        foreign = make_context(self.root, self.root / 'vault-b')
        p = self.transcript({'id': OTHER, 'cwd': str(foreign.paths.vault_root)})
        hook_input = self.state / 'hookin-foreign.json'
        hook_input.write_text(json.dumps({'session_id': SID, 'transcript_path': str(p)}), encoding='utf-8')
        model = Model('FOREIGN CLI')
        with mock.patch.object(cli, 'bootstrap', return_value=self.ctx), \
             mock.patch('respectedbrain.providers.runner.ModelRunner', return_value=model):
            status = cli.main(['flush', '--hook-input', str(hook_input)])
        daily_files = list((self.vault / 'daily').glob('*.md'))
        self.assertEqual(status, 1)
        self.assertEqual(daily_files, [])
    def test_direct_conflicting_provider_identity_rejected(self):
        p = self.transcript({'id': OTHER, 'cwd': str(self.vault)})
        status = self.run_flush(p)
        self.assertEqual(status, 1)
    def test_direct_malformed_metadata_rejected(self):
        p = self.transcript('not-an-object')
        self.hook()
        status = self.run_flush(p)
        self.assertEqual(status, 1)
    def test_conflicting_available_ids_rejected(self):
        p = self.transcript({'id': SID, 'session_id': OTHER, 'cwd': str(self.vault)})
        count = self.catch()
        self.assertEqual(count, 0)
        self.assertFalse(self.daily.exists())
    def test_nested_workspace_container_rejected(self):
        p = self.transcript({'id': SID, 'workspace': 'not-an-object'})
        self.hook()
        count = self.catch()
        self.assertEqual(count, 0)
    def test_invalid_metadata_fields_rejected(self):
        p = self.transcript({'id': 42, 'cwd': {'path': 'wrong-type'}})
        self.hook()
        count = self.catch()
        self.assertEqual(count, 0)
    def test_snapshot_change_after_classification_rejected(self):
        foreign = make_context(self.root, self.root / 'vault-b')
        p = self.transcript({'id': SID, 'cwd': str(self.vault)})
        original = F._classify_catch_up_candidate
        def classify(*args, **kwargs):
            result = original(*args, **kwargs)
            self.write(p, {'id': OTHER, 'cwd': str(foreign.paths.vault_root)}, 'FOREIGN SOURCE')
            return result
        with mock.patch.object(F, '_classify_catch_up_candidate', side_effect=classify):
            count = self.catch(Model('FOREIGN SNAPSHOT'))
        self.assertEqual(count, 0)
    def test_last_flush_only_owner_preserved(self):
        first = self.write(self.root / 'first.jsonl', marker='FIRST')
        self.assertEqual(self.run_flush(first), 0)
        state = F._session_state_path(self.state, SID)
        state.unlink()  # Legacy installation with only the supported compatibility state.
        old_daily, old_last = self.daily.read_bytes(), (self.state / 'last-flush.json').read_bytes()
        second = self.write(self.root / 'second.jsonl', marker='SECOND')
        status = self.run_flush(second, Model('SECOND'), NOW + dt.timedelta(minutes=1))
        self.assertEqual(self.daily.read_bytes(), old_daily)
        self.assertEqual(status, 1)
    def test_real_lock_timeout_cannot_transfer_ownership(self):
        first = self.write(self.root / 'first.jsonl', marker='FIRST')
        second = self.write(self.root / 'second.jsonl', marker='SECOND')
        self.assertEqual(self.run_flush(first), 0)
        state = F._session_state_path(self.state, SID)
        last = self.state / 'last-flush.json'
        old_state, old_daily, old_last = state.read_bytes(), self.daily.read_bytes(), last.read_bytes()
        locked, release = threading.Event(), threading.Event()
        real_lock = F.runtime_platform.exclusive_lock
        def owner():
            with F._session_lock_path(self.state, SID).open('a+', encoding='utf-8') as handle:
                with real_lock(handle, blocking=True) as held:
                    assert held
                    locked.set()
                    release.wait(5)
        thread = threading.Thread(target=owner)
        thread.start()
        self.assertTrue(locked.wait(5))
        def short_lock(handle, **kwargs):
            return real_lock(handle, blocking=kwargs.get('blocking', True), timeout=.05)
        try:
            with mock.patch.object(F.runtime_platform, 'exclusive_lock', side_effect=short_lock):
                status = self.run_flush(second, Model('SECOND'), NOW + dt.timedelta(minutes=1))
            changed = state.read_bytes() != old_state
            owner_transferred = json.loads(state.read_text(encoding='utf-8')).get('transcript_path') == str(second)
        finally:
            release.set()
            thread.join(5)
        retry = self.run_flush(second, Model('SECOND'), NOW + dt.timedelta(minutes=2))
        self.assertEqual(status, 1)
        self.assertEqual(retry, 1)
        self.assertFalse(changed or owner_transferred)
        self.assertEqual(state.read_bytes(), old_state)
        self.assertEqual(self.daily.read_bytes(), old_daily)
        self.assertEqual(last.read_bytes(), old_last)
    def test_rejected_different_path_preserves_all_content(self):
        p = self.transcript({'id': SID, 'cwd': str(self.vault)})
        self.assertEqual(self.run_flush(p), 0)
        state, last = F._session_state_path(self.state, SID), self.state / 'last-flush.json'
        old = {x: x.read_bytes() for x in (state, last, self.daily)}
        p2 = self.write(self.root / 'second.jsonl', marker='SECOND')
        model = Model('SECOND')
        self.assertEqual(self.run_flush(p2, model, NOW + dt.timedelta(minutes=1)), 1)
        self.assertEqual(model.calls, 0)
        self.assertTrue(all(p.read_bytes() == b for p, b in old.items()))
    def test_absent_metadata_hook_flow_still_works(self):
        p = self.transcript()
        self.hook()
        self.assertEqual(self.catch(), 1)
        self.assertTrue(self.daily.exists())
    def test_corrupt_provenance_replay_preserves_bytes(self):
        p = self.transcript({'id': SID, 'cwd': str(self.vault)})
        prov = F._session_provenance_path(self.state, SID)
        prov.write_bytes(b'{broken')
        self.assertFalse(self.hook())
        self.assertEqual(self.catch(), 0)
        self.assertEqual(prov.read_bytes(), b'{broken')
        self.assertFalse(self.daily.exists())
    def test_structurally_invalid_provenance_remains_untrusted(self):
        p = self.transcript()
        self.hook()
        prov = F._session_provenance_path(self.state, SID)
        doc = json.loads(prov.read_text(encoding='utf-8'))
        doc['workspaces'] = [42]
        prov.write_text(json.dumps(doc), encoding='utf-8')
        before = prov.read_bytes()
        count = self.catch()
        self.assertEqual(count, 0)
    def test_concurrent_hook_conflict_is_not_lost(self):
        self.transcript()
        writing, release, second_done = threading.Event(), threading.Event(), threading.Event()
        original = F._atomic_write_json
        calls = 0
        def synchronized_write(*args, **kwargs):
            nonlocal calls
            if args[0] == F._session_provenance_path(self.state, SID):
                calls += 1
                if calls == 1:
                    writing.set()
                    assert release.wait(5)
            return original(*args, **kwargs)
        results, errors = [], []
        def hook(workspace, done=None):
            try:
                results.append(F.record_hook_workspace(self.state, self.ctx.paths.vault_id,
                                                      SID, 'codex', {'cwd': str(workspace)}))
            except Exception as error:
                errors.append(str(error))
            finally:
                if done: done.set()
        first = threading.Thread(target=hook, args=(self.vault,))
        second = threading.Thread(target=hook, args=(self.root / 'foreign-workspace', second_done))
        with mock.patch.object(F, '_atomic_write_json', side_effect=synchronized_write):
            first.start()
            self.assertTrue(writing.wait(5))
            second.start()
            second_done.wait(.2)
            release.set()
            first.join(5)
            second.join(5)
        self.assertFalse(first.is_alive() or second.is_alive())
        self.assertFalse(errors, errors)
        doc = json.loads(F._session_provenance_path(self.state, SID).read_text(encoding='utf-8'))
        self.assertEqual(doc['status'], 'ambiguous')
        before = F._session_provenance_path(self.state, SID).read_bytes()
        self.assertFalse(self.hook())
        self.assertEqual(F._session_provenance_path(self.state, SID).read_bytes(), before)
        self.assertEqual(self.catch(), 0)
        self.assertFalse(self.daily.exists())
    def test_same_path_revisions_and_retries_work(self):
        p = self.transcript({'id': SID, 'cwd': str(self.vault)})
        self.assertEqual(self.run_flush(p), 0)
        self.write(p, {'id': SID, 'cwd': str(self.vault)}, 'REVISION')
        self.assertEqual(self.run_flush(p, Model('REVISION'), NOW + dt.timedelta(minutes=1)), 0)
        self.assertIn('REVISION', self.daily.read_text(encoding='utf-8'))
        self.assertNotIn('ORIGINAL', self.daily.read_text(encoding='utf-8'))

    def test_orphan_daily_without_any_checkpoint_is_not_adopted(self):
        first = self.transcript({'id': SID, 'cwd': str(self.vault)})
        self.assertEqual(self.run_flush(first), 0)
        F._session_state_path(self.state, SID).unlink()
        (self.state / 'last-flush.json').unlink()
        before = self.daily.read_bytes()
        second = self.write(self.root / 'second.jsonl', marker='SECOND')
        self.assertEqual(self.run_flush(second, Model('SECOND'), NOW + dt.timedelta(minutes=1)), 1)
        self.assertEqual(self.daily.read_bytes(), before)
        self.assertFalse(F._session_state_path(self.state, SID).exists())

    def test_compatibility_only_same_path_cannot_adopt_ownership(self):
        path = self.transcript({'id': SID, 'cwd': str(self.vault)})
        self.assertEqual(self.run_flush(path), 0)
        state = F._session_state_path(self.state, SID)
        state.unlink()
        last = self.state / 'last-flush.json'
        before = {p: p.read_bytes() for p in (last, self.daily)}
        self.write(path, {'id': SID, 'cwd': str(self.vault)}, 'REVISION')
        model = Model('REVISION')
        self.assertEqual(self.run_flush(path, model, NOW + dt.timedelta(minutes=1)), 1)
        self.assertEqual(model.calls, 0)
        self.assertFalse(state.exists())
        self.assertTrue(all(p.read_bytes() == content for p, content in before.items()))

    def test_metadata_rejections_preserve_existing_state_and_notes(self):
        foreign = make_context(self.root, self.root / 'vault-b')
        path = self.transcript({'id': SID, 'cwd': str(self.vault)})
        self.assertEqual(self.run_flush(path), 0)
        state, last = F._session_state_path(self.state, SID), self.state / 'last-flush.json'
        before = {p: p.read_bytes() for p in (state, last, self.daily)}
        for payload in ({'id': OTHER, 'cwd': str(self.vault)},
                        {'id': SID, 'cwd': str(foreign.paths.vault_root)},
                        {'id': SID, 'workspace': []}, {'id': 42, 'cwd': str(self.vault)}):
            with self.subTest(payload=payload):
                self.write(path, payload, 'REJECTED')
                model = Model('REJECTED')
                self.assertEqual(self.run_flush(path, model, NOW + dt.timedelta(minutes=1)), 1)
                self.assertEqual(model.calls, 0)
                self.assertTrue(all(p.read_bytes() == content for p, content in before.items()))

    def test_failure_retry_keeps_ownership_and_compatibility_consistent(self):
        class Failure(Model):
            def run(self, prompt, **kwargs):
                return ModelResult(None, 'codex', 'provider-timeout')
        path = self.transcript({'id': SID, 'cwd': str(self.vault)})
        self.assertEqual(self.run_flush(path, Failure()), 1)
        state, last = F._session_state_path(self.state, SID), self.state / 'last-flush.json'
        self.assertEqual(state.read_bytes(), last.read_bytes())
        self.assertEqual(json.loads(state.read_text(encoding='utf-8'))['transcript_path'], str(path))
        self.assertEqual(self.run_flush(path, Model('RETRY'), NOW + dt.timedelta(minutes=1)), 0)
        self.assertIn('RETRY', self.daily.read_text(encoding='utf-8'))

    def test_daily_failure_preserves_pending_owner_for_retry(self):
        path = self.transcript({'id': SID, 'cwd': str(self.vault)})
        model = Model()
        def fail_daily(*args, **kwargs):
            state = json.loads(F._session_state_path(self.state, SID).read_text(encoding='utf-8'))
            self.assertEqual(state['transcript_path'], str(path))
            self.assertEqual(state['status'], 'pending')
            self.assertFalse(state['pending_companion']['daily_written'])
            raise OSError('isolated daily failure')
        with mock.patch.object(F, '_upsert_daily_session', side_effect=fail_daily):
            self.assertEqual(self.run_flush(path, model), 1)
        self.assertFalse(self.daily.exists())
        self.assertEqual(self.run_flush(path, model, NOW + dt.timedelta(minutes=1)), 0)
        self.assertEqual(model.calls, 1)
        self.assertTrue(self.daily.exists())

    def test_two_vault_hook_evidence_rejects_both_catch_up_paths(self):
        other = make_context(self.root, self.root / 'vault-b')
        path = self.transcript()
        self.hook()
        self.assertTrue(F.record_hook_workspace(other.paths.state_dir, other.paths.vault_id,
                                               SID, 'codex', {'cwd': str(other.paths.vault_root)}))
        before = {p: p.read_bytes() for p in (F._session_provenance_path(self.state, SID),
                  F._session_provenance_path(other.paths.state_dir, SID))}
        self.assertEqual(self.catch(), 0)
        self.assertEqual(F.catch_up_unflushed_sessions(other, model=Model(), now=NOW, home=self.home), 0)
        self.assertTrue(all(p.read_bytes() == content for p, content in before.items()))
        self.assertFalse(self.daily.exists())
        self.assertFalse((other.paths.vault_root / 'daily/2026-10-08.md').exists())

    def test_hook_provider_conflict_remains_ambiguous_after_replay(self):
        self.hook()
        self.assertFalse(F.record_hook_workspace(self.state, self.ctx.paths.vault_id,
                                                SID, 'claude', {'cwd': str(self.vault)}))
        provenance = F._session_provenance_path(self.state, SID)
        before = provenance.read_bytes()
        self.assertEqual(json.loads(before)['status'], 'ambiguous')
        self.assertFalse(self.hook())
        self.assertEqual(provenance.read_bytes(), before)

    def test_source_change_inside_model_cannot_change_validated_prompt(self):
        path = self.transcript({'id': SID, 'cwd': str(self.vault)})
        test = self
        class Capture(Model):
            def run(self, prompt, **kwargs):
                test.write(path, {'id': OTHER, 'cwd': str(test.root / 'foreign')}, 'FOREIGN')
                test.assertIn('USER', prompt)
                test.assertNotIn('FOREIGN', prompt)
                return ModelResult(SUMMARY, 'codex', None)
        self.assertEqual(self.run_flush(path, Capture()), 0)
        self.assertIn('ORIGINAL', self.daily.read_text(encoding='utf-8'))
        self.assertNotIn('FOREIGN', self.daily.read_text(encoding='utf-8'))

    def test_precompact_cannot_archive_foreign_transcript(self):
        from respectedbrain.memory import lifecycle as L
        foreign = make_context(self.root, self.root / 'vault-b')
        path = self.transcript({'id': OTHER, 'cwd': str(foreign.paths.vault_root)})
        with mock.patch.object(L, '_launch_flush', return_value=True):
            L.handle_event(self.ctx, event='precompact', session_id=SID, transcript=path,
                           payload={'provider': 'codex', 'cwd': str(self.vault)}, now=NOW)
        self.assertEqual(list((self.vault / '🔮 850-Companion/Session-Logs').glob('*.jsonl')), [])
        self.assertFalse(F._session_state_path(self.state, SID).exists())
        self.assertFalse(self.daily.exists())

    def test_precompact_archives_valid_snapshot(self):
        from respectedbrain.memory import lifecycle as L
        path = self.transcript({'id': SID, 'cwd': str(self.vault)})
        before = path.read_bytes()
        with mock.patch.object(L, '_launch_flush', return_value=True):
            L.handle_event(self.ctx, event='precompact', session_id=SID, transcript=path,
                           payload={'provider': 'codex', 'cwd': str(self.vault)}, now=NOW)
        logs = list((self.vault / '🔮 850-Companion/Session-Logs').glob('*.jsonl'))
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].read_bytes(), before)

    def test_archived_session_cannot_be_taken_over_by_another_path(self):
        from respectedbrain.memory import lifecycle as L
        path = self.transcript({'id': SID, 'cwd': str(self.vault)})
        with mock.patch.object(L, '_launch_flush', return_value=True):
            L.handle_event(self.ctx, event='precompact', session_id=SID, transcript=path,
                           payload={'provider': 'codex', 'cwd': str(self.vault)}, now=NOW)
        second = self.write(self.root / 'other' / f'rollout-{SID}.jsonl',
                            {'id': SID, 'cwd': str(self.vault)}, 'OTHER')
        model = Model('OTHER')
        self.assertEqual(self.run_flush(second, model, NOW + dt.timedelta(minutes=1)), 1)
        self.assertEqual(model.calls, 0)
        self.assertFalse(self.daily.exists())
        self.assertEqual(self.run_flush(path, Model()), 0)
        self.assertTrue(self.daily.exists())

    def test_cli_validates_available_hook_provenance(self):
        from respectedbrain import cli
        foreign = make_context(self.root, self.root / 'vault-b')
        path = self.transcript()
        for extra in ({'cwd': str(foreign.paths.vault_root)}, {'workspace': []},
                      {'conversation_id': OTHER, 'cwd': str(self.vault)}, {'provider': 'claude'},
                      {'metadata': {'provider': 'claude'}, 'cwd': str(self.vault)}):
            with self.subTest(extra=extra):
                hook_input = self.state / 'hookin-provenance.json'
                hook_input.write_text(json.dumps({'session_id': SID, 'transcript_path': str(path),
                                                 'provider': 'codex', **extra}), encoding='utf-8')
                before = hook_input.read_bytes()
                model = Model('REJECTED')
                with mock.patch.object(cli, 'bootstrap', return_value=self.ctx), \
                     mock.patch('respectedbrain.providers.runner.ModelRunner', return_value=model):
                    status = cli.main(['flush', '--hook-input', str(hook_input)])
                self.assertEqual(status, 1)
                self.assertEqual(model.calls, 0)
                self.assertEqual(hook_input.read_bytes(), before)
                self.assertFalse(self.daily.exists())

    def test_ordinary_native_metadata_cannot_be_treated_as_absent(self):
        foreign = make_context(self.root, self.root / 'vault-b')
        path = self.transcript({'id': SID, 'cwd': str(self.vault)})
        self.assertEqual(self.run_flush(path), 0)
        before = {p: p.read_bytes() for p in (F._session_state_path(self.state, SID),
                  self.state / 'last-flush.json', self.daily)}
        for fields in ({'sessionId': OTHER, 'cwd': str(self.vault)},
                       {'sessionId': SID, 'cwd': str(foreign.paths.vault_root)},
                       {'sessionId': 42, 'cwd': str(self.vault)}):
            with self.subTest(fields=fields):
                self.write(path, records=[{'type': 'user', 'message': {'role': 'user', 'content': 'REJECTED'}, **fields}])
                model = Model('REJECTED')
                self.assertEqual(self.run_flush(path, model, NOW + dt.timedelta(minutes=1)), 1)
                self.assertEqual(model.calls, 0)
                self.assertTrue(all(p.read_bytes() == content for p, content in before.items()))

    def test_nested_metadata_and_explicit_null_are_fail_closed(self):
        foreign = make_context(self.root, self.root / 'vault-b')
        base = {'id': SID, 'cwd': str(self.vault)}
        records = [
            {'type': 'session_meta', 'payload': {**base, 'metadata': {'session_id': OTHER, 'cwd': str(foreign.paths.vault_root)}}},
            {'type': 'session_meta', 'payload': {**base, 'meta': []}},
            {'type': 'session_metadata', 'payload': None, **base},
        ]
        for record in records:
            with self.subTest(record=record):
                path = self.write(self.sessions / f'rollout-{SID}.jsonl', records=[record])
                self.hook()
                model = Model('REJECTED')
                self.assertEqual(self.run_flush(path, model), 1)
                self.assertEqual(model.calls, 0)
                self.assertFalse(F._session_state_path(self.state, SID).exists())
                self.assertFalse(self.daily.exists())

    def test_ordinary_message_id_is_not_a_session_identity(self):
        path = self.write(self.sessions / f'rollout-{SID}.jsonl', records=[
            {'type': 'session_metadata', 'id': SID, 'cwd': str(self.vault)},
            {'type': 'user', 'id': 'message-only-id', 'sessionId': SID,
             'message': {'role': 'user', 'content': 'VALID'}}])
        self.assertEqual(self.run_flush(path), 0)
        self.assertTrue(self.daily.exists())

    def test_provider_change_cannot_reinterpret_owned_session(self):
        path = self.transcript({'id': SID, 'cwd': str(self.vault)})
        self.assertEqual(self.run_flush(path), 0)
        before = {p: p.read_bytes() for p in (F._session_state_path(self.state, SID),
                  self.state / 'last-flush.json', self.daily)}
        self.write(path, {'id': SID, 'cwd': str(self.vault)}, 'REVISION')
        model = Model('REJECTED')
        with mock.patch.dict(os.environ, {'BEYIN_PROVIDER': 'claude'}):
            self.assertEqual(self.run_flush(path, model, NOW + dt.timedelta(minutes=1)), 1)
        self.assertEqual(model.calls, 0)
        self.assertTrue(all(p.read_bytes() == content for p, content in before.items()))

    def test_native_provider_path_cannot_be_mislabeled(self):
        path = self.transcript({'id': SID, 'cwd': str(self.vault)})
        model = Model()
        with mock.patch.dict(os.environ, {'BEYIN_PROVIDER': 'claude'}):
            self.assertEqual(self.run_flush(path, model), 1)
        self.assertEqual(model.calls, 0)
        self.assertFalse(F._session_state_path(self.state, SID).exists())
        self.assertFalse(self.daily.exists())

    def test_conflicting_transcript_provider_metadata_is_rejected(self):
        path = self.transcript({'id': SID, 'cwd': str(self.vault), 'provider': 'claude'})
        model = Model()
        self.assertEqual(self.run_flush(path, model), 1)
        self.assertEqual(model.calls, 0)
        self.assertFalse(self.daily.exists())

    def test_bridge_cannot_normalize_away_available_conflicts(self):
        from respectedbrain.integrations.hooks import bridge
        from respectedbrain.memory import lifecycle as L
        from respectedbrain import cli
        foreign = make_context(self.root, self.root / 'vault-b')
        path = self.transcript()
        def launch(ctx, provider, *, payload=None, **kwargs):
            hook_input = self.state / 'hookin-conflicting-source.json'
            hook_input.write_text(json.dumps(payload), encoding='utf-8')
            with mock.patch.object(cli, 'bootstrap', return_value=ctx), \
                 mock.patch('respectedbrain.providers.runner.ModelRunner', return_value=Model()):
                return cli.main(['flush', '--hook-input', str(hook_input)]) == 0
        for fields in ({'provider': 'claude', 'cwd': str(self.vault)},
                       {'cwd': str(foreign.paths.vault_root), 'workspace': {'current_dir': str(self.vault)}}):
            with self.subTest(fields=fields), mock.patch.object(L, '_launch_flush', side_effect=launch):
                bridge.dispatch(self.ctx, provider='codex', event='end', argv=[],
                                stdin=json.dumps({'session_id': SID, 'transcript_path': str(path), **fields}))
                self.assertFalse(self.daily.exists())

    def test_malformed_cursor_hook_keeps_native_response_protocol(self):
        from respectedbrain.integrations.hooks import bridge
        response = bridge.dispatch(self.ctx, provider='cursor', event='end', argv=[],
                                   stdin=json.dumps({'session_id': SID, 'workspace': []}))
        self.assertEqual(json.loads(response), {})
        self.assertFalse(self.daily.exists())

    def test_failed_session_catch_up_retry_writes_one_summary(self):
        class Failure(Model):
            def run(self, prompt, **kwargs):
                return ModelResult(None, 'codex', 'provider-timeout')
        path = self.transcript({'id': SID, 'cwd': str(self.vault)})
        self.assertEqual(self.run_flush(path, Failure()), 1)
        model = Model('RETRY')
        self.assertEqual(self.catch(model), 1)
        before = self.daily.read_bytes()
        self.assertEqual(self.catch(model), 0)
        self.assertEqual(model.calls, 1)
        self.assertEqual(self.daily.read_bytes(), before)
        self.assertEqual(before.count(b':BEGIN -->'), 1)

    def test_missing_hook_workspace_stays_absent_through_bridge(self):
        from respectedbrain.integrations.hooks import bridge
        from respectedbrain.memory import lifecycle as L
        from respectedbrain import cli
        path = self.transcript()
        def launch(ctx, provider, *, payload=None, **kwargs):
            hook_input = self.state / 'hookin-absent-workspace.json'
            hook_input.write_text(json.dumps(payload), encoding='utf-8')
            with mock.patch.object(cli, 'bootstrap', return_value=ctx), \
                 mock.patch.object(cli, 'datetime', wraps=dt.datetime) as clock, \
                 mock.patch('respectedbrain.providers.runner.ModelRunner', return_value=Model()):
                clock.now.return_value = NOW
                return cli.main(['flush', '--hook-input', str(hook_input)]) == 0
        with mock.patch.object(L, '_launch_flush', side_effect=launch):
            bridge.dispatch(self.ctx, provider='codex', event='end', argv=[],
                            stdin=json.dumps({'session_id': SID, 'transcript_path': str(path)}))
        self.assertTrue(self.daily.exists())

    def test_uuid_case_collision_is_rejected_before_any_write(self):
        self.transcript({'id': SID, 'cwd': str(self.vault)})
        self.write(self.sessions / 'other' / f'rollout-{SID.upper()}.jsonl',
                   {'id': SID, 'cwd': str(self.vault)}, 'OTHER')
        model = Model()
        self.assertEqual(self.catch(model), 0)
        self.assertEqual(model.calls, 0)
        self.assertFalse(self.daily.exists())

    def test_uuid_case_revision_uses_one_owner_and_one_daily_block(self):
        path = self.transcript({'id': SID, 'cwd': str(self.vault)})
        self.assertEqual(self.run_flush(path), 0)
        self.write(path, {'id': SID, 'cwd': str(self.vault)}, 'REVISION')
        self.assertEqual(F.flush_transcript(self.ctx, session_id=SID.upper(), transcript=path,
                         model=Model('REVISION'), now=NOW + dt.timedelta(minutes=1)), 0)
        text = self.daily.read_text(encoding='utf-8')
        self.assertEqual(text.count(':BEGIN -->'), 1)
        self.assertNotIn('ORIGINAL', text)
        self.assertIn('REVISION', text)

    def test_start_cleanup_cannot_erase_ambiguous_provenance(self):
        from respectedbrain.memory import lifecycle as L
        path = self.transcript()
        self.hook()
        self.assertFalse(F.record_hook_workspace(self.state, self.ctx.paths.vault_id, SID,
                                                'codex', {'cwd': str(self.root / 'foreign')}))
        provenance = F._session_provenance_path(self.state, SID)
        before = provenance.read_bytes()
        os.utime(provenance, (NOW.timestamp() - 8 * 86400,) * 2)
        L.start_context(self.vault, self.state, 'unrelated-session', NOW)
        self.assertTrue(provenance.exists())
        self.assertEqual(provenance.read_bytes(), before)
        self.assertFalse(self.hook())
        self.assertEqual(self.run_flush(path), 1)
        self.assertFalse(self.daily.exists())

    def test_catch_up_timestamp_uses_validated_snapshot(self):
        path = self.write(self.sessions / f'rollout-{SID}.jsonl', records=[
            {'type': 'session_meta', 'timestamp': NOW.isoformat(),
             'payload': {'id': SID, 'cwd': str(self.vault)}}])
        original = F._extract_transcript_time
        def replace_source(source, tz=None):
            before = path.read_bytes()
            self.write(path, records=[{'type': 'session_meta', 'timestamp': '1999-01-01T12:00:00+00:00',
                                      'payload': {'id': OTHER, 'cwd': str(self.root / 'foreign')}}])
            try:
                return original(source, tz)
            finally:
                path.write_bytes(before)
        with mock.patch.object(F, '_extract_transcript_time', side_effect=replace_source):
            self.assertEqual(self.catch(), 1)
        self.assertTrue(self.daily.exists())
        self.assertFalse((self.vault / 'daily/1999-01-01.md').exists())

    def test_antigravity_invocation_ids_do_not_block_stable_session_flush(self):
        from respectedbrain.integrations.hooks import bridge
        from respectedbrain.memory import lifecycle as L
        from respectedbrain import cli
        path = self.home / '.gemini/antigravity-ide/brain' / SID / '.system_generated/logs/transcript.jsonl'
        model = Model()
        statuses = []
        def launch(ctx, provider, *, payload=None, **kwargs):
            hook_input = self.state / 'hookin-antigravity.json'
            hook_input.write_text(json.dumps(payload), encoding='utf-8')
            with mock.patch.dict(os.environ, {'BEYIN_PROVIDER': provider}), \
                 mock.patch.object(cli, 'bootstrap', return_value=ctx), \
                 mock.patch.object(cli, 'datetime', wraps=dt.datetime) as clock, \
                 mock.patch('respectedbrain.providers.runner.ModelRunner', return_value=model):
                clock.now.return_value = NOW
                status = cli.main(['flush', '--hook-input', str(hook_input)])
            statuses.append(status)
            return status == 0
        for index, alias in enumerate(('conversationId', 'conversation_id')):
            self.write(path, {'id': SID, 'cwd': str(self.vault)}, f'TURN-{index}')
            model.marker = f'INVOCATION-{index}'
            with mock.patch.object(L, '_launch_flush', side_effect=launch):
                bridge.dispatch(self.ctx, provider='antigravity', event='end', argv=[],
                    stdin=json.dumps({alias: f'invocation-{index}', 'transcriptPath': str(path),
                                      'workspacePaths': [str(self.vault)]}))
        self.assertEqual(statuses, [0, 0])
        self.assertEqual(model.calls, 2)
        text = self.daily.read_text(encoding='utf-8')
        self.assertEqual(text.count(':BEGIN -->'), 1)
        self.assertIn('INVOCATION-1', text)
        self.assertNotIn('INVOCATION-0', text)
        owner = json.loads(F._session_state_path(self.state, SID).read_text(encoding='utf-8'))
        self.assertEqual(owner['session_id'], SID)
        self.assertEqual(owner['provider'], 'antigravity')

    def test_antigravity_normalization_preserves_real_identity_conflicts(self):
        from respectedbrain.integrations.hooks import bridge
        from respectedbrain.memory import lifecycle as L
        path = self.write(self.home / '.gemini/antigravity-ide/brain' / SID / '.system_generated/logs/transcript.jsonl',
                          {'id': SID, 'cwd': str(self.vault)})
        for extra in ({'session_id': OTHER}, {'metadata': {'session_id': OTHER}},
                      {'conversation_id': 'different-invocation'}):
            with self.subTest(extra=extra), mock.patch.object(L, '_launch_flush', return_value=True):
                response = bridge.dispatch(self.ctx, provider='antigravity', event='precompact', argv=[],
                    stdin=json.dumps({'conversationId': 'invocation-one', 'transcriptPath': str(path),
                                      'cwd': str(self.vault), **extra}))
                self.assertEqual(json.loads(response), {'decision': 'stop'})
                self.assertFalse(F._session_provenance_path(self.state, SID).exists())
                self.assertFalse(F._session_state_path(self.state, SID).exists())
                self.assertEqual(list((self.vault / '🔮 850-Companion/Session-Logs').glob('*.jsonl')), [])

    def test_malformed_retry_counter_does_not_abort_other_catch_up_sessions(self):
        bad = self.transcript({'id': SID, 'cwd': str(self.vault)})
        healthy = self.sessions / f'rollout-{OTHER}.jsonl'
        state = F._session_state_path(self.state, SID)
        for index, attempts in enumerate(('not-an-integer', None, True, -1, 1.5, [], {})):
            with self.subTest(attempts=attempts):
                state.write_text(json.dumps({'session_id': SID, 'transcript_path': str(bad),
                    'provider': 'codex', 'status': 'fail', 'ts': NOW.timestamp() - 60,
                    'attempts': attempts}), encoding='utf-8')
                before = state.read_bytes()
                self.write(healthy, {'id': OTHER, 'cwd': str(self.vault)}, f'HEALTHY-{index}')
                model = Model(f'HEALTHY-{index}')
                try:
                    count = self.catch(model)
                except (ValueError, TypeError) as error:
                    self.fail(f'One corrupt counter aborted catch-up: {error}')
                self.assertEqual(count, 1)
                self.assertEqual(model.calls, 1)
                self.assertEqual(state.read_bytes(), before)
                report = json.loads((self.state / 'catch-up-report.json').read_text(encoding='utf-8'))
                self.assertIn((SID, 'session-state-invalid'),
                              [(entry['session_id'], entry['reason']) for entry in report['ambiguous']])
                self.assertIn(f'HEALTHY-{index}', self.daily.read_text(encoding='utf-8'))

    def test_model_session_markers_cannot_poison_daily_or_block_retry(self):
        path = self.transcript({'id': SID, 'cwd': str(self.vault)})
        self.assertEqual(self.run_flush(path), 0)
        identity = hashlib.sha256(f'codex\0{SID}'.encode()).hexdigest()
        markers = [f'<!-- RESPECTED-SESSION:{identity}:{kind} -->' for kind in ('BEGIN', 'END')]
        markers.append('<!-- RESPECTED-SESSION:foreign-session:BEGIN -->')
        for index, marker in enumerate(markers):
            with self.subTest(marker=marker):
                before = self.daily.read_bytes()
                self.write(path, {'id': SID, 'cwd': str(self.vault)}, f'REVISION-{index}')
                self.assertEqual(self.run_flush(path, Model(marker), NOW + dt.timedelta(minutes=2 * index + 1)), 1)
                self.assertEqual(self.daily.read_bytes(), before)
                self.assertEqual(self.run_flush(path, Model('RECOVERED'), NOW + dt.timedelta(minutes=2 * index + 2)), 0)
                text = self.daily.read_text(encoding='utf-8')
                self.assertEqual(text.count(':BEGIN -->'), 1)
                self.assertEqual(text.count(':END -->'), 1)
                self.assertIn('RECOVERED', text)

    def test_invalid_pending_fields_preserve_checkpoint_and_never_run_model(self):
        path = self.transcript({'id': SID, 'cwd': str(self.vault)})
        with mock.patch.object(F, '_upsert_daily_session', side_effect=OSError('daily failure')):
            self.assertEqual(self.run_flush(path), 1)
        state_path = F._session_state_path(self.state, SID)
        original = json.loads(state_path.read_text(encoding='utf-8'))
        missing = object()
        cases = {
            'daily_written': ('false', 0, 1, None, [], {}, missing),
            'provider': ('claude', 'unknown', '', None, [], missing),
            'event_time': ('invalid', '2026-10-08T12:00:00', '', None, missing),
            'reason': ('unknown', '', None, [], missing),
            'summary': ('invalid', 'FLUSH_BOS', '', None, [], missing),
        }
        compatibility = (self.state / 'last-flush.json').read_bytes()
        for field, values in cases.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    state = json.loads(json.dumps(original))
                    if value is missing:
                        del state['pending_companion'][field]
                    else:
                        state['pending_companion'][field] = value
                    state_path.write_text(json.dumps(state), encoding='utf-8')
                    before = state_path.read_bytes()
                    model = Model('MUST NOT RUN')
                    self.assertEqual(self.run_flush(path, model, NOW + dt.timedelta(minutes=1)), 1)
                    self.assertEqual(model.calls, 0)
                    self.assertFalse(self.daily.exists())
                    self.assertEqual(state_path.read_bytes(), before)
                    self.assertEqual((self.state / 'last-flush.json').read_bytes(), compatibility)

    def test_invalid_owned_state_fields_cannot_be_overwritten(self):
        path = self.transcript({'id': SID, 'cwd': str(self.vault)})
        with mock.patch.object(F, '_upsert_daily_session', side_effect=OSError('daily failure')):
            self.assertEqual(self.run_flush(path), 1)
        state_path = F._session_state_path(self.state, SID)
        original = json.loads(state_path.read_text(encoding='utf-8'))
        cases = {
            'ts': (float('nan'), float('inf'), float('-inf'), True, None),
            'turns': (True, -1, 1.5, '1', None),
            'transcript_hash': ('wrong', '', None, 1, []),
            'attempts': (True, -1, 1.5, '1', None),
            'pending_companion': (None, [], 'wrong'),
        }
        for field, values in cases.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    state = {**original, field: value}
                    state_path.write_text(json.dumps(state), encoding='utf-8')
                    before = state_path.read_bytes()
                    model = Model('MUST NOT RUN')
                    self.assertEqual(self.run_flush(path, model, NOW + dt.timedelta(minutes=1)), 1)
                    self.assertEqual(model.calls, 0)
                    self.assertEqual(state_path.read_bytes(), before)
                    self.assertFalse(self.daily.exists())

    def test_pending_daily_written_requires_one_durable_block(self):
        path = self.transcript({'id': SID, 'cwd': str(self.vault)})
        with mock.patch.object(F, '_record_session_event', side_effect=OSError('projection failure')):
            self.assertEqual(self.run_flush(path), 1)
        state_path = F._session_state_path(self.state, SID)
        before_state = state_path.read_bytes()
        original_daily = self.daily.read_bytes()
        for daily in (None, b'# Human replacement\r\n', original_daily + original_daily,
                      original_daily.replace(b':END -->', b':BROKEN -->')):
            with self.subTest(daily=daily):
                if daily is None:
                    self.daily.unlink(missing_ok=True)
                else:
                    self.daily.write_bytes(daily)
                model = Model('MUST NOT RUN')
                self.assertEqual(self.run_flush(path, model, NOW + dt.timedelta(days=1)), 1)
                self.assertEqual(model.calls, 0)
                self.assertEqual(state_path.read_bytes(), before_state)
                self.assertEqual(self.daily.read_bytes() if self.daily.exists() else None, daily)

    def test_invalid_pending_candidate_does_not_block_healthy_catch_up(self):
        bad = self.transcript({'id': SID, 'cwd': str(self.vault)})
        with mock.patch.object(F, '_upsert_daily_session', side_effect=OSError('daily failure')):
            self.assertEqual(self.run_flush(bad), 1)
        state_path = F._session_state_path(self.state, SID)
        state = json.loads(state_path.read_text(encoding='utf-8'))
        state['pending_companion']['daily_written'] = 'false'
        state_path.write_text(json.dumps(state), encoding='utf-8')
        before = state_path.read_bytes()
        self.write(self.sessions / f'rollout-{OTHER}.jsonl', {'id': OTHER, 'cwd': str(self.vault)})
        model = Model('HEALTHY')
        self.assertEqual(self.catch(model), 1)
        self.assertEqual(model.calls, 1)
        self.assertEqual(state_path.read_bytes(), before)
        self.assertEqual(self.daily.read_text(encoding='utf-8').count(':BEGIN -->'), 1)
        report = json.loads((self.state / 'catch-up-report.json').read_text(encoding='utf-8'))
        failed = [entry for entry in report['accepted'] if entry['session_id'] == SID]
        self.assertEqual(failed[0]['result'], 'failed:session-pending-invalid')

    def test_daily_writer_rejects_reserved_markers_before_touching_human_text(self):
        self.daily.parent.mkdir()
        self.daily.write_bytes(b'# HUMAN DAILY\r\nKeep these bytes.\r\n')
        before = self.daily.read_bytes()
        for kind in ('BEGIN', 'END'):
            with self.subTest(kind=kind):
                with self.assertRaisesRegex(OSError, 'daily-summary-markers-invalid'):
                    F._upsert_daily_session(self.vault, self.state,
                        SUMMARY + f'\n<!-- RESPECTED-SESSION:foreign-session:{kind} -->',
                        'turn', NOW, SID, 'codex')
                self.assertEqual(self.daily.read_bytes(), before)

    def test_corrupt_health_payload_cannot_crash_rejected_flush(self):
        path = self.transcript({'id': OTHER, 'cwd': str(self.vault)})
        health = self.state / 'health.json'
        health.write_text('{"unknown": NaN}', encoding='utf-8')
        model = Model('MUST NOT RUN')
        self.assertEqual(self.run_flush(path, model), 1)
        self.assertEqual(model.calls, 0)
        self.assertFalse(self.daily.exists())
        self.assertEqual(json.loads(health.read_text(encoding='utf-8'))['error'],
                         'provider-session-id-mismatch')

    def test_invalid_reason_is_rejected_before_creating_a_checkpoint(self):
        path = self.transcript({'id': SID, 'cwd': str(self.vault)})
        for reason in ('unknown', '', None, [], {}):
            with self.subTest(reason=reason):
                model = Model('MUST NOT RUN')
                self.assertEqual(F.flush_transcript(self.ctx, session_id=SID, transcript=path,
                    model=model, now=NOW, reason=reason), 1)
                self.assertEqual(model.calls, 0)
                self.assertFalse(F._session_state_path(self.state, SID).exists())
                self.assertFalse(self.daily.exists())

if __name__ == '__main__':
    unittest.main()
