"""Legacy entry point: rebuild blanks from the rounded numbered meshes."""

from pathlib import Path
import subprocess
import sys

if __name__ == "__main__":
    folder = Path(__file__).resolve().parent
    for script in ("sync-blank-dice.py", "align-dice.py"):
        subprocess.run([sys.executable, str(folder / script)], check=True)
