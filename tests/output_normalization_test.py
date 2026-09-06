#!/usr/bin/env python3
"""Tests for model output normalization and single schema retry (Faz 1)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
FLUSH_PATH = ROOT / "template/.beyin/engine/flush.py"


def load_flush_module():
    spec = importlib.util.spec_from_file_location("flush_module", FLUSH_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALID_SUMMARY = """## Bağlam
Furkan ile Respected Brain mimarisi üzerine çalışıldı.

## Önemli Konuşmalar
1.4.0 yol haritasındaki güvenilirlik ve event mimarisi değerlendirildi.

## Alınan Kararlar
Faz 1 kapsamında model çıktısı normalizasyonu ve pycache temizliği uygulanacak.

## Öğrenilenler
Preamble soyma ve 1-shot şema retry'ı token tasarrufu sağlar.

## Yapılacaklar
- RED testleri tamamla
- flush.py onarım fonksiyonunu ekle
"""

INVALID_SUMMARY_BAD_HEADINGS = """İşte yaptığımız konuşmanın özeti:
- Birinci konu konuşuldu
- Kararlar alındı
- Başka bir şey yok
"""


class OutputNormalizationTest(unittest.TestCase):
    def setUp(self):
        self.flush = load_flush_module()

    def test_clean_summary_is_preserved(self):
        normalized = self.flush.normalize_summary(VALID_SUMMARY)
        self.assertEqual(normalized, VALID_SUMMARY.strip())

    def test_flush_bos_is_preserved(self):
        normalized = self.flush.normalize_summary("FLUSH_BOS")
        self.assertEqual(normalized, "FLUSH_BOS")

    def test_preamble_is_stripped_cleanly(self):
        chatter = "Elbette! İşte istediğiniz oturum özeti:\n\n" + VALID_SUMMARY
        normalized = self.flush.normalize_summary(chatter)
        self.assertEqual(normalized, VALID_SUMMARY.strip())

    def test_markdown_code_fences_are_stripped(self):
        wrapped = "```markdown\n" + VALID_SUMMARY + "\n```"
        normalized = self.flush.normalize_summary(wrapped)
        self.assertEqual(normalized, VALID_SUMMARY.strip())

    def test_chatter_with_markdown_fence_is_stripped(self):
        wrapped = "İşte özet:\n```markdown\n" + VALID_SUMMARY + "\n```"
        normalized = self.flush.normalize_summary(wrapped)
        self.assertEqual(normalized, VALID_SUMMARY.strip())

    def test_invalid_headings_return_none(self):
        normalized = self.flush.normalize_summary(INVALID_SUMMARY_BAD_HEADINGS)
        self.assertIsNone(normalized)

    def test_single_schema_retry_on_invalid_output(self):
        """When the first model call returns invalid schema, it must attempt exactly one repair."""
        self.assertTrue(
            hasattr(self.flush, "repair_summary_schema") or hasattr(self.flush, "_repair_summary_schema"),
            "flush module must provide a schema repair helper",
        )
        repair_func = getattr(self.flush, "repair_summary_schema", None) or getattr(self.flush, "_repair_summary_schema")

        with mock.patch.object(self.flush, "_run_model", return_value=(VALID_SUMMARY, None)) as mock_run:
            with tempfile.TemporaryDirectory() as temp_dir:
                vault_root = Path(temp_dir)
                repaired = repair_func(INVALID_SUMMARY_BAD_HEADINGS, vault_root)
                self.assertEqual(repaired, VALID_SUMMARY.strip())
                self.assertEqual(mock_run.call_count, 1)

                sent_prompt = mock_run.call_args[0][0]
                self.assertIn(INVALID_SUMMARY_BAD_HEADINGS.strip(), sent_prompt)
                self.assertIn("## Bağlam", sent_prompt)
                self.assertNotIn("UNTRUSTED TRANSCRIPT DATA", sent_prompt)

    def test_schema_retry_fails_closed_after_single_attempt(self):
        """If repair attempt still returns invalid schema, it must return None and not retry infinitely."""
        repair_func = getattr(self.flush, "repair_summary_schema", None) or getattr(self.flush, "_repair_summary_schema", None)
        if repair_func is None:
            self.fail("repair_summary_schema helper not yet implemented")

        with mock.patch.object(self.flush, "_run_model", return_value=(INVALID_SUMMARY_BAD_HEADINGS, None)) as mock_run:
            with tempfile.TemporaryDirectory() as temp_dir:
                vault_root = Path(temp_dir)
                repaired = repair_func(INVALID_SUMMARY_BAD_HEADINGS, vault_root)
                self.assertIsNone(repaired)
                self.assertEqual(mock_run.call_count, 1)

    def test_end_to_end_flush_recovers_via_single_repair(self):
        """When initial flush produces invalid schema, the 1-shot repair succeeds and completes the flush."""
        call_count = 0

        def fake_run_model(prompt, vault_root):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call returns invalid schema
                return INVALID_SUMMARY_BAD_HEADINGS, None
            # Second call (repair) returns valid schema
            return VALID_SUMMARY, None

        with tempfile.TemporaryDirectory() as temp_dir:
            vault_root = Path(temp_dir)
            state_dir = vault_root / ".claude" / "scripts" / ".state"
            state_dir.mkdir(parents=True, exist_ok=True)
            daily_dir = vault_root / "daily"

            transcript_path = vault_root / "transcript.jsonl"
            transcript_path.write_text(
                '{"role": "user", "content": "1.4.0 için güvenilirlik geliştirmeleri"}\n'
                '{"role": "assistant", "content": "Tek şema retry uygulandı."}\n',
                encoding="utf-8",
            )
            hook_input = state_dir / "hookin-test.json"
            hook_input.write_text(
                f'{{"session_id": "repair-test-1", "transcript_path": "{transcript_path.as_posix()}"}}',
                encoding="utf-8",
            )

            with mock.patch.object(self.flush, "VAULT_ROOT", vault_root), \
                 mock.patch.object(self.flush, "STATE_DIR", state_dir), \
                 mock.patch.object(self.flush, "_run_model", side_effect=fake_run_model):

                exit_code = self.flush.main([
                    "--hook-input", str(hook_input),
                    "--reason", "sessionend",
                ])
                self.assertEqual(exit_code, 0)
                self.assertEqual(call_count, 2)

                # Daily file should now exist and contain the valid repaired summary
                daily_files = list(daily_dir.glob("*.md"))
                self.assertEqual(len(daily_files), 1)
                daily_content = daily_files[0].read_text(encoding="utf-8")
                self.assertIn("## Bağlam", daily_content)
                self.assertIn("Faz 1 kapsamında model çıktısı normalizasyonu", daily_content)

                # State file should indicate success
                state_file = state_dir / "last-flush.json"
                self.assertTrue(state_file.exists())
                import json
                state_data = json.loads(state_file.read_text(encoding="utf-8"))
                self.assertEqual(state_data.get("status"), "ok")
                self.assertEqual(state_data.get("detail"), "appended")


if __name__ == "__main__":
    unittest.main()
