"""Export a source-only snapshot; not a general secret scanner or security audit."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = (".gitignore", "Cargo.toml", "Cargo.lock", "README.md")
SOURCE_DIRS = ("docs", "firmware", "prover", "scripts", "tests", "vendor", "verifier")
SKIP_DIRS = {
    ".git", ".hg", ".svn", ".pio", ".tools", ".cargo-home", ".venv", "venv",
    "__pycache__", "target", "target-xtensa", "node_modules", "managed_components",
    "secrets", "artifacts", "backup", "backups", ".vscode", ".idea", ".zed",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".claude",
}
SKIP_SUFFIXES = {
    ".pyc", ".pyo", ".exe", ".dll", ".pdb", ".rlib", ".rmeta", ".a", ".o",
    ".obj", ".bin", ".hex", ".pem", ".key", ".p12", ".pfx", ".rs.bk",
}


def excluded(path):
    relative = path.relative_to(ROOT)
    name = path.name.lower()
    for prefix in ("vendor/zkmcu/fuzz/seeds", "vendor/zkmcu/fuzz/runs",
                   "vendor/zkmcu/fuzz/corpus", "vendor/zkmcu/research/out",
                   "vendor/zkmcu/research/blog-drafts"):
        if relative.is_relative_to(prefix):
            return True
    if any(part.lower() in SKIP_DIRS for part in relative.parts):
        return True
    if name in {".git", ".ds_store", "thumbs.db", "policy_generated.h", "claude.md"}:
        return True
    if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
        return True
    if name.startswith("config.local."):
        return True
    if name.endswith(".json") and (name.startswith("credential-") or name.startswith("registry")):
        return True
    if relative.parent == Path("firmware") and name.startswith("sdkconfig."):
        return name != "sdkconfig.defaults"
    return any(name.endswith(suffix) for suffix in SKIP_SUFFIXES)


def source_files():
    for name in SOURCE_FILES:
        path = ROOT / name
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"missing or linked required source: {name}")
        yield path
    for path in sorted(ROOT.glob("LICENSE*")):
        if path.is_file() and not path.is_symlink():
            yield path
    for name in SOURCE_DIRS:
        directory = ROOT / name
        if not directory.is_dir() or directory.is_symlink():
            raise ValueError(f"missing or linked source directory: {name}")
        pending = [directory]
        while pending:
            for path in sorted(pending.pop().iterdir()):
                if excluded(path):
                    continue
                if path.is_symlink() or path.is_junction():
                    raise ValueError(f"linked source needs manual review: {path.relative_to(ROOT)}")
                if path.is_dir():
                    pending.append(path)
                elif path.is_file():
                    yield path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/public-release"))
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise ValueError("output already exists; choose a new directory")
    if output == ROOT or (output.is_relative_to(ROOT) and not output.is_relative_to(ROOT / "artifacts")):
        raise ValueError("inside the working project, export only below artifacts/")
    files = sorted(source_files())
    for path in files:
        if not path.resolve().is_relative_to(ROOT):
            raise ValueError("source resolves outside the project")
    output.mkdir(parents=True, exist_ok=False)
    manifest = []
    for source in files:
        relative = source.relative_to(ROOT)
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        manifest.append({"path": relative.as_posix(),
                         "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
                         "bytes": destination.stat().st_size})
    (output / "PUBLICATION-MANIFEST.json").write_text(
        json.dumps({"format": 1, "files": manifest}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "files": len(manifest),
                      "bytes": sum(item["bytes"] for item in manifest),
                      "project_license_present": (output / "LICENSE").is_file(),
                      "review": "Review the snapshot and select a project license before publishing."},
                     indent=2))


if __name__ == "__main__":
    main()
