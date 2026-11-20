"""Cargo with project-local dependency/cache/output paths; no global configuration edits."""
import os
import pathlib
import subprocess
import sys
root = pathlib.Path(__file__).resolve().parents[1]
env = os.environ.copy()
env["CARGO_HOME"] = str(root / ".cargo-home")
env["CARGO_TARGET_DIR"] = str(root / "target")
raise SystemExit(subprocess.call(["cargo", *sys.argv[1:]], cwd=root, env=env))

