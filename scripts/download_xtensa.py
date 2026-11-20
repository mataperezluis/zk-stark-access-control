"""Fetch official Espressif compiler artifacts, contained in this project only."""
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile
import tarfile

root = Path(__file__).resolve().parents[1]
out = root / ".tools" / "downloads"
out.mkdir(parents=True, exist_ok=True)
version = "1.97.0.0"
base = f"https://github.com/esp-rs/rust-build/releases/download/v{version}/"
names = [f"rust-{version}-x86_64-pc-windows-msvc.zip", f"rust-src-{version}.tar.xz"]
expected = ["43eadbfd09c411d9a93768a2fa92063adc23f10f1b0fd28703e266ab40e98e74",
            "568d688b9f8f332ec4d04657544fad23e99ce11e9e6cf5835979e68a28c68b73"]
records = []
for name, expected_hash in zip(names, expected):
    target = out / name
    if not target.exists():
        partial = target.with_name(target.name + ".part")
        with urllib.request.urlopen(base + name, timeout=60) as response, partial.open("wb") as stream:
            while chunk := response.read(1024 * 1024):
                stream.write(chunk)
        partial.replace(target)
    with target.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != expected_hash:
        raise ValueError(f"compiler artifact hash mismatch: {name}")
    records.append({"name": name, "url": base + name,
                    "sha256": digest,
                    "bytes": target.stat().st_size})
(out / "manifest.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
if not (root / ".tools/esp/bin/rustc.exe").exists():
    with zipfile.ZipFile(out / names[0]) as archive:
        destination = (root / ".tools").resolve()
        for name in archive.namelist():
            if not (destination / name).resolve().is_relative_to(destination):
                raise ValueError("unsafe zip member")
        archive.extractall(destination)
if not (root / ".tools/rust-src/rust-src-nightly/rust-src/lib/rustlib/src/rust/library/Cargo.toml").exists():
    with tarfile.open(out / names[1]) as archive:
        archive.extractall(root / ".tools/rust-src", filter="data")
print(json.dumps(records, indent=2))
