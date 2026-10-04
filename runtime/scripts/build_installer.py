"""Source build adapter; tools/build_installer.py owns native packaging."""
from pathlib import Path
import runpy

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parents[2] / "tools" / "build_installer.py"), run_name="__main__")
