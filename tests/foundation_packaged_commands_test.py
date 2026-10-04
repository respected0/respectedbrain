"""Installed workflow command contracts; parsing never executes model/process actions."""
from contextlib import redirect_stdout
import io
import ast
import re
import shlex
import unittest
from pathlib import Path
from respectedbrain.cli import _parser
from respectedbrain.core.resources import ResourceCatalog
from respectedbrain.maintenance import _TOOLS

class FoundationPackagedCommandsTest(unittest.TestCase):
    def documents(self):
        resources=ResourceCatalog()
        return {name:resources.read_text("skills/"+name) for name in resources.iter_files("skills") if name.endswith(".md")} | {"instructions/default.md":resources.read_text("instructions/default.md")}
    def test_installed_guides_do_not_execute_retired_vault_or_checkout_engines(self):
        for name,text in self.documents().items():
            with self.subTest(name=name):
                self.assertNotRegex(text,r"\.beyin/|\.claude/scripts/|scripts/[\w-]+\.py")
                blocks=re.findall(r"```(?!python)([^\n]*)\n(.*?)```",text,re.S)
                for language,body in blocks:
                    self.assertNotRegex(body,r"(?m)^\s*(?:python3?|py(?:\.exe)? -3)\s")
    def test_native_examples_parse_against_public_cli_and_known_maintenance_tools(self):
        found=[]
        for name,text in self.documents().items():
            for line in text.splitlines():
                if not line.startswith("respectedbrain "):
                    continue
                with self.subTest(name=name,command=line):
                    words=shlex.split(line)
                    if words[1:]==["--version"]:
                        with redirect_stdout(io.StringIO()),self.assertRaises(SystemExit) as result:
                            _parser().parse_args(words[1:])
                        self.assertEqual(result.exception.code,0)
                        continue
                    args=_parser().parse_args(words[1:])
                    self.assertFalse(args.command.startswith("_"))
                    if args.command=="maintenance":
                        self.assertIn(args.name,_TOOLS)
                        module_path=Path(__file__).resolve().parents[1]/"src/respectedbrain/maintenance"/(_TOOLS[args.name].lstrip(".").replace(".","/")+".py")
                        syntax=ast.parse(module_path.read_text(encoding="utf-8"))
                        flags={item.value for node in ast.walk(syntax) if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=="add_argument" for item in node.args if isinstance(item,ast.Constant) and isinstance(item.value,str)}
                        for value in args.argv:
                            if value.startswith("--"):
                                self.assertIn(value.split("=",1)[0],flags)
                    if args.command=="orchestrate":
                        source=Path(__file__).resolve().parents[1]/"src/respectedbrain/orchestration/runner.py"
                        syntax=ast.parse(source.read_text(encoding="utf-8"))
                        flags={item.value for node in ast.walk(syntax) if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=="add_argument" for item in node.args if isinstance(item,ast.Constant) and isinstance(item.value,str)}
                        for value in args.argv:
                            if value.startswith("--") and value!="--":
                                self.assertIn(value.split("=",1)[0],flags)
                    if args.command in ("maps","compile","search","maintenance","orchestrate","repair","dashboard"):
                        self.assertIsNotNone(args.vault_id,"Installed examples must select the registered UUID")
                    found.append((name,args.command))
        self.assertGreaterEqual(len(found),12,"Installed workflows need actionable native CLI examples")
        self.assertTrue({"compile","maps","search","maintenance","orchestrate","configure","vault"}.issubset({command for name,command in found}))
    def test_instructions_explain_registered_identity_and_separate_state(self):
        text=self.documents()["instructions/default.md"]
        for token in ("DataRoot", "VaultRoot", "AppRoot", "--vault-id", "RESPECTED_DATA_DIR", "vaults/<UUID>/state", "vaults/<UUID>/cache"):
            self.assertIn(token,text)

    def test_export_algorithm_reference_still_parses_and_preserves_data_safety(self):
        text=self.documents()["gecmis-import/SKILL.md"]
        blocks=re.findall(r"```python\n(.*?)```",text,re.S)
        self.assertEqual(len(blocks),3)
        for block in blocks:
            ast.parse(block)
        for token in ("def walk_nodes", "def write_exclusive", "MAX_EXPORT_BYTES = 50 * 1024 * 1024", "RECENT_MONTHS = 12", "MAX_FILE_CHARS = 200000", "native CLI", "exclusive-create", "İkinci açık onay"):
            self.assertIn(token,text)

    def test_installed_diagnosis_uses_real_marker_and_packaged_seeds(self):
        documents = self.documents()
        self.assertIn(".respected.json", ResourceCatalog().iter_files("vault-template"))
        for name in ("instructions/default.md", "beyin-doktor/SKILL.md"):
            self.assertIn("VaultRoot/.respected.json", documents[name])
            self.assertNotIn("VaultRoot/respectedbrain.json", documents[name])
        doctor = documents["beyin-doktor/SKILL.md"]
        self.assertNotIn("depodaki tohum", doctor)
        for resource in ("vault-template/knowledge/index.md", "vault-template/🔮 850-Companion/Kurallar.md"):
            self.assertTrue(ResourceCatalog().read_text(resource))
            self.assertIn(resource, doctor)
