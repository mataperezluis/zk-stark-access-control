# Zero-Knowledge Authorization on an ESP32-S3

An ESP32-S3 maintenance gateway that verifies cryptographic proofs locally before
executing protected commands. A computer generates the proof; the private credential
and membership path stay on the computer.

Built with Rust, Plonky3, Python, ESP-IDF and PlatformIO as an experiment in
AI-assisted embedded development.

## How it works

A zero-knowledge proof lets someone demonstrate a statement while keeping the
private information behind it hidden. Here, the intended statement is:
**"I know a credential belonging to the device's authorized registry."**

The computer is the **prover** and the ESP32 is the **verifier**:

```text
Computer                         ESP32-S3
         operation + argument ->
         <- fresh challenge
         proof + public inputs -> local verification
         <- result
```

Each proof is bound to a fresh challenge and a specific operation. The application
supports protected diagnostics, entering maintenance mode, setting a RAM
configuration value from 0 to 100, and leaving maintenance mode. Challenges expire
after 60 seconds; maintenance lasts 30 seconds and each protected command requires
its own proof.

## Requirements

- **Hardware:** ESP32-S3 with 8 MiB octal PSRAM, 16 MiB flash, JD9853 LCD and
  AXS5106 touch controller. Check the [wiring and board details](docs/hardware-compatibility.md).
- **Windows/PowerShell:** the supplied build wrappers and executable paths target Windows.
- **Python 3.12+**, **Rust/Cargo** (tested with 1.94.0), and the Windows C++ build tools.
- **PlatformIO Core**, with `pio` available in the terminal.

## Build and upload

Run these commands from the repository root. Replace `COM5` with your device's
port and close other serial monitors before using USB.

### 1. Set up Python and build the Rust components

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r prover/requirements.txt
python scripts/download_xtensa.py
python scripts/cargo.py build -p access-zk --release --locked
python scripts/cargo_xtensa.py build -p access-zk-embedded --release --target xtensa-esp32s3-none-elf --locked
```

Required Plonky3 sources are included under `vendor/`. The downloader installs the
pinned Xtensa Rust toolchain locally and verifies its SHA-256 hashes.

### 2. Generate credentials and the device policy

For a fresh checkout:

```powershell
.\target\release\access-zk.exe init secrets/demo
.\target\release\access-zk.exe policy-header secrets/demo/registry.json firmware/include/policy_generated.h
```

These commands generate four credentials and a matching public policy. They refuse
to overwrite existing files. **Keep `secrets/` private**; credentials are not
encrypted at rest. Without a generated policy, the device denies authorization.

### 3. Build and upload the firmware

```powershell
pio run --project-dir firmware
pio run --project-dir firmware --target upload --upload-port COM5
```

Use the PlatformIO terminal if `pio` is not on your normal terminal's path.
Uploading replaces the board's current application.

## Try it

```powershell
.\.venv\Scripts\python.exe -m prover.usb info --port COM5
.\.venv\Scripts\python.exe -m prover.usb auth --port COM5 --operation diagnostics
.\.venv\Scripts\python.exe -m prover.usb auth --port COM5 --operation enter
.\.venv\Scripts\python.exe -m prover.usb auth --port COM5 --operation set --value 42
.\.venv\Scripts\python.exe -m prover.usb auth --port COM5 --operation exit
```

Run `set` within the 30-second maintenance window. The default credential is
`secrets/demo/credential-0.json`; select another with `--credential PATH`.
Touch selects an operation; authorization still requires a proof over USB.

## Tests and benchmarks

Host tests:

```powershell
python scripts/cargo.py test -p access-zk --release --locked
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

With a provisioned board and matching credentials:

```powershell
.\.venv\Scripts\python.exe -m tests.device_security --port COM5 --long
.\.venv\Scripts\python.exe -m scripts.benchmark --port COM5 --count 5
```

The long device tests exercise real operations and wait for actual expirations.
The benchmark updates `docs/benchmark-results.json`.

Recorded on November 10, 2026: five fresh diagnostic requests, ESP32-S3 at
**160 MHz**, with display rendering active.

| Measurement | Recorded result |
| --- | --- |
| Host proof generation, median | 257 ms |
| USB proof transfer, median | 1.105 s |
| Local ESP32 verification, median | 1.845 s |
| Complete request to decision, median | 3.292 s |
| Proof size | Approximately 383 kB |

See [full measurements and validation](docs/benchmarks.md) for methodology,
memory measurements and test evidence.

## Scope and documentation

This is an **unaudited research prototype**. The custom proof construction needs
independent review; there is no claim of overall 128-bit or established
post-quantum security. USB is not encrypted, and physical device protection and
denial-of-service hardening remain outside the implementation.

- [Architecture](docs/architecture.md)
- [Cryptographic design and credential revocation](docs/cryptographic-design.md)
- [USB protocol](docs/protocol.md)
- [Threat model](docs/threat-model.md)

## License

Original project code is licensed under the [MIT License](LICENSE).
Third-party licenses and asset attribution are documented in
[third-party notices](docs/third-party-notices.md).

