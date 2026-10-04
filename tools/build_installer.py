"""Build one native, self-contained application and its hash inventory."""
from __future__ import annotations
import argparse
import hashlib
from importlib.metadata import version
import json
import os
import plistlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def dereference_distribution_links(app: Path) -> None:
    """Flatten internal PyInstaller links; reject escapes and directory cycles first."""
    if app.is_symlink():
        raise ValueError("Distribution root must be a regular directory")
    root = app.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Distribution root must be a directory")
    if not any(path.is_symlink() for path in root.rglob("*")):
        return

    def copy(node: Path, target: Path, ancestors: frozenset[Path]) -> None:
        try:
            resolved = node.resolve(strict=True)
        except (OSError, RuntimeError) as error:
            raise ValueError(f"Unresolvable distribution link: {node}") from error
        if not resolved.is_relative_to(root):
            raise ValueError(f"Distribution link escapes package: {node}")
        if resolved.is_dir():
            if resolved in ancestors:
                raise ValueError(f"Distribution directory link cycle: {node}")
            target.mkdir()
            for child in sorted(resolved.iterdir()):
                copy(child, target / child.name, ancestors | {resolved})
            shutil.copystat(resolved, target)
        elif resolved.is_file():
            shutil.copy2(resolved, target)
        else:
            raise ValueError(f"Unsupported distribution member: {node}")

    with tempfile.TemporaryDirectory(prefix=".respected-links-", dir=root.parent) as temporary:
        staging = Path(temporary) / "normalized"
        copy(root, staging, frozenset())
        original = Path(temporary) / "original"
        root.rename(original)
        try:
            staging.rename(root)
        except BaseException:
            original.rename(root)
            raise


def assemble_macos_bundle(source: Path, bundle: Path) -> None:
    """Place onedir contents where the macOS bootloader resolves its library root."""
    if bundle.is_symlink():
        raise ValueError("Bundle destination must not be a link")
    bundle.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".respected-bundle-", dir=bundle.parent) as temporary:
        staging = Path(temporary) / bundle.name
        executable_dir = staging / "Contents/MacOS"
        executable_dir.mkdir(parents=True)
        shutil.copy2(source / "respectedbrain", executable_dir / "respectedbrain")
        # PyInstaller recognizes .app/Contents/MacOS even for its console
        # bootloader and uses Contents/Frameworks, ignoring --contents-directory.
        shutil.copytree(source / "app", staging / "Contents/Frameworks")
        with (staging / "Contents/Info.plist").open("wb") as stream:
            plistlib.dump({"CFBundleExecutable": "respectedbrain",
                          "CFBundleIdentifier": "com.respected.respectedbrain",
                          "CFBundleName": "Respected Brain",
                          "CFBundlePackageType": "APPL"}, stream)
        original = Path(temporary) / "original"
        existed = bundle.exists()
        if existed:
            bundle.rename(original)
        try:
            staging.rename(bundle)
        except BaseException:
            if existed:
                original.rename(bundle)
            raise


def build(*, platform: str, output: Path, installer: bool = True) -> Path:
    native = "windows" if sys.platform == "win32" else "macos" if sys.platform == "darwin" else "linux"
    if platform != native:
        raise ValueError("Frozen distributions must be built on their native platform")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--contents-directory", "app", "--name", "RespectedBrain", "--distpath", str(output), "--workpath", str(ROOT / "build/frozen"), "--specpath", str(ROOT / "build"), "--paths", str(ROOT / "src"), "--collect-submodules", "respectedbrain", "--copy-metadata", "respectedbrain", "--add-data", str(ROOT / "src/respectedbrain/resources") + os.pathsep + "respectedbrain/resources", str(ROOT / "packaging/entrypoint.py")]
    subprocess.run(command, cwd=ROOT, check=True)
    app = output / "RespectedBrain"
    launcher = app / ("RespectedBrain.exe" if platform == "windows" else "RespectedBrain")
    target = app / ("respectedbrain.exe" if platform == "windows" else "respectedbrain")
    launcher.replace(target)
    if platform != "windows":
        dereference_distribution_links(app)
    if platform == "macos":
        bundle = output / "RespectedBrain.app"
        assemble_macos_bundle(app, bundle)
        app, target = bundle, bundle / "Contents/MacOS/respectedbrain"
    files = {path.relative_to(app).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(app.rglob("*")) if path.is_file() and path.name != "distribution.json"}
    document = {"schema_version": 3, "version": version("respectedbrain"), "platform": platform, "launcher": target.relative_to(app).as_posix(), "files": files}
    (app / "distribution.json").write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if platform != "windows":
        entry = ROOT / ("packaging/macos/setup.command" if platform == "macos" else "packaging/linux/setup.sh")
        wrapper = output / entry.name
        wrapper.write_bytes(entry.read_text(encoding="utf-8").encode("utf-8"))
        wrapper.chmod(0o755)
    if platform == "windows" and installer:
        compiler = os.environ.get("INNO_COMPILER") or shutil.which("ISCC.exe")
        if compiler is None:
            candidate = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Inno Setup 6/ISCC.exe"
            compiler = str(candidate) if candidate.is_file() else None
        if compiler is None:
            raise RuntimeError("Inno compiler is required for the Windows installer")
        subprocess.run([compiler, "/DMyAppVersion=" + document["version"], "/DPayloadDir=" + str(app), "/DOutputDir=" + str(output), str(ROOT / "packaging/windows/respected_setup.iss")], check=True)
    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", required=True, choices=("windows", "macos", "linux"))
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--no-installer", action="store_true")
    args = parser.parse_args()
    print(build(platform=args.platform, output=args.output, installer=not args.no_installer))
