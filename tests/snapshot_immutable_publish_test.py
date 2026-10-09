'''Immutable Git snapshot publication regressions.'''
from pathlib import Path
import os, shutil, subprocess, sys, tempfile, unittest
from unittest import mock
from respectedbrain.maintenance.backup.publish_git_snapshot import publish_if_due

class ImmutableSnapshotPublicationTest(unittest.TestCase):
    def setUp(self):
        if shutil.which('git') is None: self.skipTest('git is not available')
    def _git(self, repo, *args, check=True):
        result = subprocess.run(['git',*args],cwd=repo,check=check,capture_output=True)
        return result.stdout.decode().strip()
    def _fixture(self, root):
        remote = root/'remote.git'; repo = root/'vault'
        subprocess.run(['git','init','--bare',str(remote)],check=True,capture_output=True)
        subprocess.run(['git','init','-b','main',str(repo)],check=True,capture_output=True)
        self._git(repo,'config','user.name','Fixture'); self._git(repo,'config','user.email','fixture@example.invalid')
        self._git(repo,'remote','add','origin',str(remote)); (repo/'safe.md').write_text('safe')
        self._git(repo,'add','safe.md'); self._git(repo,'commit','-m','baseline'); self._git(repo,'push','-u','origin','main')
        return remote, repo

    def test_post_scan_isolated_index_race_cannot_change_published_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); remote, repo = self._fixture(root); secret = 'sk-proj-SYNTHETICONLY1234567890'*3
            import os, respectedbrain.maintenance.backup.publish_git_snapshot as module
            def race(*args,**kwargs):
                if not Path(kwargs['index_file']).name.startswith('index.tree_'):
                    return True,[]
                isolated = next((repo/'.git').glob('index.snapshot_*'))
                (repo/'race.md').write_text(secret)
                subprocess.run(['git','add','race.md'],cwd=repo,env={**os.environ,'GIT_INDEX_FILE':str(isolated)},check=True,capture_output=True)
                (repo/'race.md').unlink(); return True,[]
            with mock.patch.object(module,'scan_git_index_for_secrets',side_effect=race):
                result = publish_if_due(repo,remote='origin',branch='main',apply=True,receipt_file=root/'receipt.json')
            self.assertEqual(result['status'],'ok',result); self.assertEqual(self._git(remote,'grep','-I','-n',secret,'main',check=False),'')

    def test_staged_secret_surviving_only_in_user_index_cannot_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); remote, repo = self._fixture(root); secret = 'sk-proj-SYNTHETICONLY1234567890'*3
            mixed = repo / 'mixed.md'
            mixed.write_text(secret)
            self._git(repo, 'add', 'mixed.md')
            mixed.write_text('safe working tree content')
            before_index = (repo/'.git'/'index').read_bytes()
            result = publish_if_due(repo, remote='origin', branch='main', apply=True, receipt_file=root/'receipt.json')
            self.assertEqual(result['status'], 'aborted:secret_found', result)
            self.assertEqual(self._git(remote, 'grep', '-I', '-n', secret, 'main', check=False), '')
            self.assertEqual((repo/'.git'/'index').read_bytes(), before_index)

    def test_clean_filter_cannot_inject_secret_into_scanned_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); remote, repo = self._fixture(root); secret = 'sk-proj-SYNTHETICONLY1234567890'*3
            script = root / 'inject_secret.py'
            script.write_text(f"import sys\nsys.stdout.write({secret!r})\n", encoding='utf-8')
            command = '"{}" "{}"'.format(sys.executable.replace('\\','/'), str(script).replace('\\','/'))
            self._git(repo, 'config', 'filter.leak.clean', command)
            (repo/'.gitattributes').write_text('*.filtered filter=leak\n')
            (repo/'content.filtered').write_text('safe source')
            self._git(repo, 'add', '.gitattributes')
            self.assertIn('filter: leak', self._git(repo, 'check-attr', 'filter', 'content.filtered'))
            self._git(repo, 'add', 'content.filtered')
            self.assertEqual(self._git(repo, 'show', ':content.filtered'), secret)
            result = publish_if_due(repo, remote='origin', branch='main', apply=True, receipt_file=root/'receipt.json')
            self.assertEqual(result['status'], 'aborted:secret_found', result)
            self.assertEqual(self._git(remote, 'grep', '-I', '-n', secret, 'main', check=False), '')

    def test_tracked_ignored_file_and_user_index_head_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); remote, repo = self._fixture(root); (repo/'kept.md').write_text('tracked safe note')
            self._git(repo,'add','kept.md'); (repo/'.gitignore').write_text('kept.md\n')
            before_index = (repo/'.git'/'index').read_bytes(); before_head = self._git(repo,'rev-parse','HEAD')
            result = publish_if_due(repo,remote='origin',branch='main',apply=True,receipt_file=root/'receipt.json')
            self.assertEqual(result['status'],'ok',result)
            self.assertEqual(self._git(remote,'cat-file','-p','main:kept.md',check=False),'tracked safe note')
            self.assertEqual((repo/'.git'/'index').read_bytes(),before_index); self.assertEqual(self._git(repo,'rev-parse','HEAD'),before_head)

if __name__ == '__main__': unittest.main()
