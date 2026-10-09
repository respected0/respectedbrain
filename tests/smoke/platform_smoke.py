#!/usr/bin/env python3
"""Physical host package smoke; all registration files and vault data use a temp workspace."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[2]
PROVIDERS=("antigravity","gemini","codex","cursor","claude")
SUMMARY="""## Bağlam
Smoke bağlam

## Önemli Konuşmalar
Smoke konuşma

## Alınan Kararlar
Smoke karar

## Öğrenilenler
Smoke öğrenim

## Yapılacaklar
- Smoke tamamla
"""

def distribution_name():
    return "RespectedBrain.app" if sys.platform=="darwin" else "RespectedBrain"

def workspace_paths(root):
    # macOS bootloader recognizes the .app suffix when locating Frameworks.
    app_name="RespectedBrain.app" if sys.platform=="darwin" else "app"
    return tuple(root / name for name in ("Furkan Smoke 🧠",app_name,"data","home"))

def _run(command,*,env,cwd):
    started=time.perf_counter()
    result=subprocess.run(command,cwd=cwd,env=env,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=180,creationflags=0x08000000 if os.name=="nt" else 0)
    return result.returncode,(result.stdout+result.stderr)[-4000:],time.perf_counter()-started

def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def clean_environment(package,workspace):
    names=("PATH","SystemRoot","WINDIR","COMSPEC","PATHEXT","TEMP","TMP","TMPDIR","LOCALAPPDATA","USERPROFILE","HOME","USER","LOGNAME","SHELL","LANG","LC_ALL")
    env={name:os.environ[name] for name in names if name in os.environ}
    env.update({"PYTHONUTF8":"1","PYTHONIOENCODING":"utf-8","RESPECTED_SMOKE_PACKAGE":str(package),"RESPECTED_SMOKE_WORKSPACE":str(workspace)})
    return env

def provider_fixture(root,env):
    bin_dir=root / "fixture-bin"
    bin_dir.mkdir()
    helper=bin_dir / "summary_model.py"
    helper.write_text("import sys\nsys.stdout.reconfigure(encoding='utf-8')\nprint(" + repr(SUMMARY) + ")\n",encoding="utf-8")
    if os.name=="nt":
        script=bin_dir / "claude.cmd"
        command=subprocess.list2cmdline([sys.executable,str(helper)])
        script.write_text("@echo off\r\nmore > nul\r\n" + command + "\r\n",encoding="utf-8")
    else:
        script=bin_dir / "claude"
        command=shlex.join([sys.executable,str(helper)])
        script.write_text("#!/bin/sh\ncat >/dev/null\nexec " + command + "\n",encoding="utf-8")
        script.chmod(0o755)
    env["PATH"]=str(bin_dir)+os.pathsep+env.get("PATH","")
    return env

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path)
    parser.add_argument("--package",type=Path,default=Path(os.environ.get("RESPECTED_SMOKE_PACKAGE",str(ROOT / "dist" / distribution_name()))))
    parser.add_argument("--keep",action="store_true")
    parser.add_argument("--unsigned-fixture",action="store_true")
    parser.add_argument("--fixture-provenance",action="store_true")
    parser.add_argument("--strict-lifecycle",action="store_true")
    args=parser.parse_args(argv)
    if args.unsigned_fixture and args.fixture_provenance:
        raise ValueError("Unsigned and fixture-provenance modes are mutually exclusive")
    if args.strict_lifecycle and args.unsigned_fixture:
        raise ValueError("Strict lifecycle cannot use an unsigned fixture")
    host="windows-native" if os.name=="nt" else "wsl" if os.environ.get("WSL_DISTRO_NAME") else "macos" if sys.platform=="darwin" else "linux"
    profile_name="windows-native" if os.name=="nt" else "posix"
    root=Path(tempfile.mkdtemp(prefix="respected-package-smoke-")).resolve()
    vault,app,data,home=workspace_paths(root)
    home.mkdir()
    package=args.package.resolve()
    env=clean_environment(package,root)
    env.update({"RESPECTED_APP_DIR":str(app),"RESPECTED_DATA_DIR":str(data),"HOME":str(home),"USERPROFILE":str(home)})
    env=provider_fixture(root,env)
    if args.fixture_provenance:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from tests.foundation_install_support import fixture_gh_path, write_fixture_attestation
        package=root / "fixture-package"
        shutil.copytree(args.package.resolve(),package)
        write_fixture_attestation(package)
        fixture_path=str(fixture_gh_path(root))
        env["PATH"]=fixture_path+os.pathsep+env.get("PATH","")
        os.environ["PATH"]=fixture_path+os.pathsep+os.environ.get("PATH","")
    checks=[]
    def record(name,passed,detail="",duration=0):
        checks.append({"name":name,"status":"VERIFIED" if passed else "FAILED","detail":detail[:500],"duration_seconds":round(duration,3)})
        if not passed: raise RuntimeError(name+": "+detail)
    try:
        from respectedbrain.installation.payload import validate_package
        document=validate_package(package, require_provenance=not args.unsigned_fixture)
        record("clean-environment-has-no-product-bypass",all(key not in env for key in ("RESPECTED_ALLOW_UNSIGNED","BEYIN_LLM_COMMAND","PYTHONPATH")))
        record("strict-provenance-consumer-path",not args.unsigned_fixture)
        expected_platform="windows" if os.name=="nt" else "macos" if sys.platform=="darwin" else "linux"
        record("host-matching-real-distribution",document.get("platform")==expected_platform,str(document.get("platform")))
        lifecycle_driver=ROOT / "tests" / "smoke" / "lifecycle_driver.py"
        def lifecycle(action):
            command=[sys.executable,str(lifecycle_driver),action,"--app-root",str(app),"--data-root",str(data),"--vault",str(vault),"--home",str(home)]
            if action in ("setup","update","deferred-update"): command += ["--package",str(package)]
            if action == "setup":
                command += ["--summary-provider","claude"]
            else:
                command += ["--vault-id",ctx.paths.vault_id]
            if args.unsigned_fixture: command += ["--allow-unsigned-fixture"]
            return _run(command,env=env,cwd=root)
        code,output,elapsed=lifecycle("setup")
        record("transactional-fresh-package-install",code==0,output,elapsed)
        if args.strict_lifecycle: record("strict-default-provenance-policy",True)
        launcher=app / document["launcher"]
        code,output,elapsed=_run([str(launcher),"--version"],env=env,cwd=root)
        record("installed-frozen-launcher-version",code==0 and output.strip()==document["version"],output,elapsed)
        from respectedbrain.core.config import ConfigStore
        from respectedbrain.core.paths import Roots
        from respectedbrain.vault.registry import build_context
        from respectedbrain.integrations.backend import ExternalChange,IntegrationProfile,NativeBackend
        from respectedbrain.integrations.rendering import plan_integrations
        from respectedbrain.installation.transaction import Transaction
        from respectedbrain.installation.operations import operation_manifest
        from respectedbrain.installation.ownership import read_manifest,manifest_document
        ctx=build_context(Roots(app,data,vault),ConfigStore(data),vault=vault,vault_id=None,env={})
        code,output,elapsed=lifecycle("repair")
        record("strict-frozen-repair",code==0,output,elapsed)
        record("uuid-state-separated-from-pure-vault",ctx.paths.state_dir.is_relative_to(data) and not (vault / ".beyin").exists())
        backend=NativeBackend(data,user_home=home)
        profile=IntegrationProfile(profile_name,(str(launcher),),home)
        prior=read_manifest(data / "install-manifest.json")
        # Only temp-home file/MCP registrations are applied, never live scheduler/registry/shortcuts.
        changes=plan_integrations(ctx,profile,{"global":True,"mcp":True},backend)
        record("all-five-providers-rendered-without-legacy-engine",all(any(provider in change.key for change in changes) for provider in (".agents", ".gemini", ".codex", ".cursor", ".claude")))
        record("registration-boundary-is-temporary-files",all(row.kind in ("file","mcp") and (Path(row.key).is_relative_to(home) or Path(row.key).is_relative_to(data)) for row in changes))
        with Transaction(data,backend) as tx:
            for row in changes: tx.apply_external(row)
            owned = {(row.kind, row.key): row for row in prior.external}
            for row in changes:
                old = owned.get((row.kind, row.key))
                owned[(row.kind, row.key)] = ExternalChange(row.kind, row.key, old.before if old else row.before, row.after)
            tx.write_json(data / "install-manifest.json",manifest_document(operation_manifest(ctx,prior.files,tuple(owned.values()),previous=prior)))
            tx.commit()
        record("global-registration-retains-owned-project-hooks",all(row in read_manifest(data / "install-manifest.json").external for row in prior.external))
        record("five-provider-temp-home-global-and-mcp-registration",all(backend.read(row.kind,row.key)==row.after for row in changes))
        transcript=root / "synthetic-transcript.jsonl"
        for revision in (1,2):
            transcript.write_text(json.dumps({"role":"user","content":"synthetic turn "+str(revision)})+"\n"+json.dumps({"role":"assistant","content":"synthetic answer"})+"\n",encoding="utf-8")
            code,output,elapsed=_run([str(launcher),"flush","--vault-id",ctx.paths.vault_id,"--session-id","physical-smoke-session","--transcript",str(transcript),"--reason","turn"],env=env,cwd=root)
            record("turn-flush-revision-"+str(revision),code==0,output,elapsed)
        daily_files=list((vault / "daily").glob("*.md"))
        record("one-daily-log",len(daily_files)==1)
        daily=daily_files[0]
        body=daily.read_text(encoding="utf-8")
        record("turn-flush-upserts-one-complete-session",body.count("### Oturum")==1 and body.count("<!-- RESPECTED-SESSION:")==2 and "Smoke bağlam" in body)
        daily_hash=_sha256(daily)
        for number in (1,2):
            code,output,elapsed=lifecycle("update")
            record("transactional-update-"+str(number),code==0,output,elapsed)
        record("update-preserves-daily-byte-for-byte",_sha256(daily)==daily_hash)
        if os.name=="nt":
            if args.unsigned_fixture:
                code,output,elapsed=lifecycle("deferred-update")
                pending={}
            else:
                code,output,elapsed=_run([str(launcher),"update","--vault-id",ctx.paths.vault_id,"--package",str(package)],env=env,cwd=root)
                pending=json.loads(output) if code==0 else {}
            record("strict-deferred-package-update",code==0 and '"pending": true' in output,output,elapsed)
            receipt=data / "backups" / pending.get("tx_id","missing") / "result.json"
            # Deferred self-update stages the full product tree and journals ~2000 files with
            # fsync (plus real-time AV scanning), so allow several minutes on Windows.
            deadline=time.monotonic()+300
            while time.monotonic()<deadline and not receipt.is_file(): time.sleep(.1)
            receipt_document=json.loads(receipt.read_text(encoding="utf-8")) if receipt.is_file() else {}
            record("deferred-receipt-success",bool(receipt_document.get("success")),str(receipt_document),0)
        else:
            record("strict-deferred-package-update",True,"NOT APPLICABLE: deferred self-update is Windows-only",0)
        sentinel=home / "keep-user-file.txt"
        sentinel.write_bytes(b"keep")
        code,output,elapsed=lifecycle("uninstall")
        record("transactional-owned-only-uninstall",code==0,output,elapsed)
        record("uninstall-preserves-notes-state-and-user-file",_sha256(daily)==daily_hash and ctx.paths.state_dir.exists() and sentinel.read_bytes()==b"keep")
        record("uninstall-restores-original-temp-home-registration",all(backend.read(row.kind,row.key)==row.before for row in changes))
        local_hooks=(".agents/hooks.json",".claude/settings.json",".codex/hooks.json",".cursor/hooks.json",".gemini/settings.json")
        record("uninstall-removes-owned-project-hooks",all(not (vault / name).exists() for name in local_hooks))
    except Exception as error:
        if not checks or checks[-1]["status"]!="FAILED": checks.append({"name":"smoke-runner","status":"FAILED","detail":str(error),"duration_seconds":0})
    provenance_mode="fixture-policy" if args.fixture_provenance else "unsigned-fixture" if args.unsigned_fixture else "production"
    report={"schema_version":3,"host":host,"profile":profile_name,"platform":platform.platform(),"python":{"version":platform.python_version(),"executable":sys.executable},"wsl_distribution":os.environ.get("WSL_DISTRO_NAME"),"providers":list(PROVIDERS),"package":str(package),"provenance_mode":provenance_mode,"workspace":str(root) if args.keep else "deleted-after-run","checks":checks,"overall":"VERIFIED" if checks and all(row["status"]=="VERIFIED" for row in checks) else "FAILED"}
    rendered=json.dumps(report,ensure_ascii=False,indent=2)+"\n"
    if args.output:
        target=args.output.expanduser().resolve()
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(rendered,encoding="utf-8")
    print(rendered,end="")
    if not args.keep:
        assert root.parent==Path(tempfile.gettempdir()).resolve() and root.name.startswith("respected-package-smoke-")
        shutil.rmtree(root)
    return 0 if report["overall"]=="VERIFIED" else 1

if __name__=="__main__":
    raise SystemExit(main())
