"""Verify that original source/configuration files retain their pre-task SHA-256 hashes."""
import hashlib
import json
from pathlib import Path
root = Path(__file__).resolve().parents[1]
baseline = json.loads((root / "docs/original-files-sha256.json").read_text(encoding="utf-8-sig"))
failures = []
for item in baseline:
    target = root.parent / item["path"]
    if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest().upper() != item["sha256"]:
        failures.append(item["path"])
report = {"original_files_checked":len(baseline), "unchanged":not failures, "changed":failures}
(root / "docs/isolation-result.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps(report))
raise SystemExit(bool(failures))

