"""Use the project-local Espressif toolchain; never register a global rustup toolchain."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
root = Path(__file__).resolve().parents[1]
toolchain = root / ".tools/esp"
source = root / ".tools/rust-src/rust-src-nightly/rust-src/lib/rustlib/src/rust/library"
destination = toolchain / "lib/rustlib/src/rust/library"
if source.exists() and not (destination / "Cargo.toml").exists():
    shutil.copytree(source, destination, dirs_exist_ok=True)
env = os.environ.copy()
env["CARGO_HOME"] = str(root / ".cargo-home")
env["CARGO_TARGET_DIR"] = str(root / "target-xtensa")
env["RUSTC"] = str(toolchain / "bin/rustc.exe")
env["RUSTDOC"] = str(toolchain / "bin/rustdoc.exe")
env["PATH"] = str(toolchain / "bin") + os.pathsep + env["PATH"]
raise SystemExit(subprocess.call([str(toolchain / "bin/cargo.exe"),
    "-Zbuild-std=core,alloc,panic_abort", *sys.argv[1:]], cwd=root, env=env))

