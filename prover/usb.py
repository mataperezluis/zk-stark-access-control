"""Run: python -m prover.usb info|status|auth --port COM5."""
import argparse
import json
from pathlib import Path
import subprocess
import time
import uuid
from .transport import Client

ROOT = Path(__file__).resolve().parents[1]
BINARY = ROOT / "target/release/access-zk.exe"
OPERATIONS = {"diagnostics": 1, "enter": 2, "set": 3, "exit": 4}

def generate(wallet, context, directory=None):
    directory = directory or ROOT / "artifacts" / ("session-" + uuid.uuid4().hex)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "context.bin").write_bytes(context)
    command = [str(BINARY), "prove", str(wallet), str(directory / "context.bin"),
               str(directory / "proof.bin"), str(directory / "public.bin")]
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    return ((directory / "proof.bin").read_bytes(), (directory / "public.bin").read_bytes(),
            json.loads(completed.stdout), directory)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("info", "status", "auth"))
    parser.add_argument("--port", required=True)
    parser.add_argument("--credential", type=Path, default=ROOT / "secrets/demo/credential-0.json")
    parser.add_argument("--operation", choices=(*OPERATIONS, "selected"), default="diagnostics")
    parser.add_argument("--value", type=int, default=0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    client = Client(args.port)
    try:
        if args.command == "info":
            data = client.info()
        elif args.command == "status":
            data = client.status()
        else:
            op = client.status()["selected_operation"] if args.operation == "selected" else OPERATIONS[args.operation]
            started = time.perf_counter()
            ident, context, _ = client.request(op, args.value)
            proof, public, host, directory = generate(args.credential, context)
            data = client.upload(ident, proof, public)
            data["host"] = host
            data["host_total_ms"] = round((time.perf_counter() - started) * 1000, 3)
            data["artifacts"] = str(directory.relative_to(ROOT))
        print(json.dumps(data, indent=2))
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(data, indent=2), encoding="utf-8")
        if data.get("code", 0) != 0:
            raise SystemExit(2)
    finally:
        client.close()

if __name__ == "__main__":
    main()

