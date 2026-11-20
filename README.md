# Zero-Knowledge Authorization on an ESP32-S3

A research prototype that verifies cryptographic membership proofs **locally on an
ESP32-S3** before executing protected maintenance operations. A computer generates
the proof; the private credential and membership path are not sent to the device.

Built with Rust, Plonky3, Python, ESP-IDF and PlatformIO. This repository accompanies
an experiment in AI-assisted embedded development.

**Research software:** the custom construction has no independent security audit
or application-level zero-knowledge proof. It is not a production access controller.
See [security and limitations](#security-and-limitations).

## What is a zero-knowledge proof?

A zero-knowledge proof lets a prover demonstrate a statement while keeping the
private information behind it hidden. Here, the intended statement is:

> I know a credential belonging to the device's authorized registry, and this proof
> is bound to the current challenge and requested operation.

The computer is the **prover**. The ESP32-S3 is the **verifier** and makes its own
authorization decision. The operation, its argument and request context are public;
zero knowledge does not make the USB connection confidential.

## What the application does

Each privileged operation requires a fresh, operation-specific proof:

| Operation | Behavior |
| --- | --- |
| `diagnostics` | Read the protected RAM configuration and device measurements |
| `enter` | Enter maintenance mode for 30 seconds |
| `set --value N` | Set a noncritical RAM parameter to 0..100 while maintenance is active |
| `exit` | Leave maintenance mode |

The parameter starts at 25 and resets on reboot. A device challenge expires after
60 seconds and is single-use. Changing the operation, value, device/boot context or
policy invalidates a proof. Failure closes maintenance access. Touch selects an
operation; execution still requires a proof from the host.

## Architecture

```text
Computer                                      ESP32-S3
Python USB client + Rust prover                ESP-IDF C++ + Rust verifier

              operation + argument ---------->
              <---------- fresh challenge and public context
Private credential + membership path
              proof + public inputs ---------> local verification
              <---------- decision and measurements

The private credential remains on the computer.
```

The active implementation is `access-zk`: an adaptation of zkmcu's membership AIR
(the algebraic constraints defining a valid computation), using the pinned
Plonky3 fork's **hiding FRI PCS, salted Merkle commitments and fresh ChaCha20
randomness**. The `no_std` Rust verifier is linked into ESP-IDF through a C ABI.
Proof storage and verifier allocations use PSRAM.

## Repository layout

| Path | Contents |
| --- | --- |
| `firmware/` | ESP-IDF/PlatformIO application, display, touch and PSRAM allocator |
| `verifier/zkmcu-zk/` | Active Rust proof library, host CLI and security tests |
| `verifier/embedded/` | Embedded Rust static library |
| `prover/*.py` | Python USB client and framing |
| `tests/` | Python framing tests and real-device test programs |
| `scripts/` | Build wrappers, toolchain download, measurements and source export |
| `vendor/` | Plonky3 sources, selected AIR reference files, pins and upstream licenses |
| `docs/` | Design, protocol, threat model and recorded measurements |

`secrets/`, `artifacts/`, build outputs and downloaded toolchains are local-only.
The generated `firmware/include/policy_generated.h` is also excluded: each new
installation generates its own registry and matching public policy.

## Hardware and prerequisites

The tested board has an **ESP32-S3 rev 0.2, 8 MiB octal PSRAM and 16 MiB flash**,
with a JD9853 172 x 320 LCD and AXS5106 touch controller. The generic PlatformIO
profile name `esp32-s3-devkitc-1` does not imply that every board with that profile
has this memory or wiring. LCD initialization is part of authorization readiness.
Check [hardware compatibility and pins](docs/hardware-compatibility.md) before
using another board.

The provided build wrappers and host executable paths target **Windows/PowerShell**.
Other operating systems require adaptations and have not been validated.

- Python **3.12+** for the setup/export scripts; `python` must resolve to a real
  Python installation rather than the Windows Store execution alias.
- Rust/Cargo on `PATH`; host builds were recorded with stable **1.94.0**. The
  workspace includes Rust 2024 code and is not compatible with older compilers.
- PlatformIO Core, with `pio` available on `PATH`. Recorded configuration: Core
  6.2.0, Espressif32 7.1.3, ESP-IDF package 4.60100.0 / ESP-IDF 6.1.0.
- The host Rust toolchain's required native linker/build tools, normally Visual
  Studio C++ Build Tools and a Windows SDK for an MSVC toolchain.
- Internet access for the initial toolchain/package downloads; enough disk space
  for the project-local Rust tools and build caches.
- A data-capable USB cable connected to the board's native USB Serial/JTAG port.

Run all commands below from the directory containing **this README and Cargo.toml**.
`COM5` is an example: replace it with your board's actual port. Close serial monitors
before using the USB client or uploading firmware.

## Setup and first build

### 1. Install the Python host dependency

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r prover/requirements.txt
```

Only `pyserial` is required by the USB client. The virtual environment does not need
activation when its interpreter is called explicitly.

### 2. Build the host prover and embedded verifier

The Plonky3 sources are required Cargo path dependencies and must be included in a
source checkout. Their pinned revision and license files are under `vendor/`.
The zkmcu directory contains only the AIR reference sources and design material
used by this application; see `vendor/zkmcu/README.md`. No recursive submodule
download is required for a publication snapshot.

```powershell
python scripts/download_xtensa.py
python scripts/cargo.py build -p access-zk --release --locked
python scripts/cargo_xtensa.py build -p access-zk-embedded --release --target xtensa-esp32s3-none-elf --locked
```

The downloader checks pinned SHA-256 hashes for Espressif's Windows Rust toolchain
artifacts. The wrappers place Cargo downloads in `.cargo-home/`, host output in
`target/`, embedded output in `target-xtensa/`, and the Xtensa toolchain under
`.tools/`. They do not register a global rustup toolchain.

### 3. Generate your own credentials and public policy

For a **fresh checkout**:

```powershell
.\target\release\access-zk.exe init secrets/demo
.\target\release\access-zk.exe policy-header secrets/demo/registry.json firmware/include/policy_generated.h
```

`init` creates four random credentials in a 1,024-slot registry. The practical
anonymity set is those four enrolled members, not 1,024 operators. Credential files
are unencrypted; keep them and the registry administration files private.

These commands deliberately refuse to overwrite an existing registry, credential
or policy header. On an existing installation, retain the matching files or choose
new output locations; deleting the credentials does not create a recoverable setup.

The policy header contains a **public root and epoch**, not credential secrets.
Without a generated policy, the device starts restricted and denies authorization.
Without the real Rust verifier library, firmware configuration fails.

### 4. Build and upload the firmware

```powershell
pio run --project-dir firmware
pio run --project-dir firmware --target upload --upload-port COM5
```

If `pio` is not on `PATH`, use the PlatformIO terminal or replace it with:

```powershell
& "$env:USERPROFILE\.platformio\penv\Scripts\platformio.exe" run --project-dir firmware
```

Uploading replaces the program on the board. Save an appropriate private backup of
any previous firmware first. This project does not enable Secure Boot, flash
encryption, JTAG restrictions or eFuses; it does not implement OTA.

## Run a maintenance operation

```powershell
.\.venv\Scripts\python.exe -m prover.usb info --port COM5
.\.venv\Scripts\python.exe -m prover.usb status --port COM5
.\.venv\Scripts\python.exe -m prover.usb auth --port COM5 --operation diagnostics
.\.venv\Scripts\python.exe -m prover.usb auth --port COM5 --operation enter
.\.venv\Scripts\python.exe -m prover.usb auth --port COM5 --operation set --value 42
.\.venv\Scripts\python.exe -m prover.usb auth --port COM5 --operation exit
```

The default credential is `secrets/demo/credential-0.json`; choose another using
`--credential PATH`. Run `set` within the 30-second maintenance window; it requires
both the active window and its own value-specific proof. Public `status` redacts
the protected configuration.

To prove the operation selected on the touchscreen, use `--operation selected`.
Touch never grants access by itself. The setting value is supplied on the host
using `--value`.

## Tests and measurements

Host-only checks do not need a connected board:

```powershell
python scripts/cargo.py test -p access-zk --release --locked -- --nocapture
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The following programs operate on the **real board** and require a provisioned
policy, matching credentials and exclusive serial access:

```powershell
.\.venv\Scripts\python.exe -m tests.device_security --port COM5 --long
.\.venv\Scripts\python.exe -m scripts.benchmark --port COM5 --count 5
python scripts/write_benchmark_report.py
.\.venv\Scripts\python.exe -m prover.usb auth --port COM5 --operation diagnostics --output artifacts/measurement.json
```

The long tests wait for actual 60-second challenge and 30-second maintenance
expirations. The benchmark writes `docs/benchmark-results.json`; the report writer
updates `docs/benchmarks.md`. Save the recorded evidence before replacing it with
your own measurements.

An additional lifecycle test **reflashes the device with a temporary policy**, tests
revocation, then attempts to restore the initial policy/firmware in a `finally`
block. Interruption or power loss can require manual restoration. Run it only when
you intend to perform that policy rotation:

```powershell
.\.venv\Scripts\python.exe -m tests.policy_lifecycle --port COM5
```

That test currently locates PlatformIO at the default Windows installation path.
`scripts/check_isolation.py` is a historical check against the original neighboring
weather/HMAC projects; it is not a standalone-checkout validation command.

## Recorded results

Five fresh diagnostic requests were measured on **November 10, 2026**, with the
ESP32-S3 at **160 MHz**, 8 MiB PSRAM at 40 MHz, and display rendering active.

| Measurement | Recorded result |
| --- | --- |
| Host proof generation, median | 257.443 ms |
| Host USB proof transfer, median | 1,105.110 ms |
| Local ESP32 verification, median | 1,845.470 ms |
| Complete host request to decision, median | 3,292.214 ms |
| Proof size | 382,823-382,986 bytes |
| Rust verifier peak live allocation payload on ESP32 | 543,232 bytes |
| Firmware binary size | 441,008 bytes |

The Rust allocation measurement excludes proof storage, task stacks and allocator
overhead. Verification time excludes proof reception; display rendering runs
concurrently. Five requests are initial measurements, not an exhaustive performance
study. See [measurement boundaries and validation](docs/benchmarks.md) and
[raw benchmark data](docs/benchmark-results.json).

Recorded validation includes eight Rust security tests, four Python framing tests,
17 integration groups (16 involving the board), and real policy rotation. These
cover authorization, changed proofs/public context, replay, expiration and revoked
policy handling. Automated LCD transfers and touch-controller probing were
observed; full human visual/touch-coordinate validation remains separate.

## Credential revocation

```powershell
.\target\release\access-zk.exe revoke secrets/demo/registry.json 0 secrets/registry-epoch2.json
.\target\release\access-zk.exe refresh secrets/registry-epoch2.json secrets/demo/credential-1.json secrets/credential-1-epoch2.json
.\target\release\access-zk.exe policy-header secrets/registry-epoch2.json artifacts/policy-epoch2.h
```

Install the new public policy header, rebuild, and upload the firmware to activate
the new root/epoch. Remaining members need refreshed membership paths. Revocation
is effective only after the device policy is updated; there is no unauthenticated
USB policy-update command. Preserve the old policy securely if restoration is needed.

## Security and limitations

- The custom AIR and hiding configuration need independent review. Randomized
  proof bytes and passing tests do not establish a complete zero-knowledge guarantee.
- Six BabyBear digest elements provide about 185.4 output bits, giving at most
  about **92.7 bits of generic classical collision resistance**. There is no claim
  of overall 128-bit security or established post-quantum security.
- USB is neither encrypted nor peer-authenticated. Operations, context and timing
  are visible; live proof relaying is outside the implemented protection.
- Host compromise and physical device compromise are outside the privacy claim.
  Private files and flash backups depend on host/account storage protection.
- Adversarial proofs can consume resources or trigger panic/allocation resets.
  This implementation is not hardened against denial of service.
- Physical reflashing can replace firmware or restore an older policy. Secure Boot,
  flash encryption, rollback protection and authenticated live updates are absent.
- ML-DSA policy updates and ML-KEM sessions are future work, not implemented features.

See the [threat model](docs/threat-model.md), [cryptographic design](docs/cryptographic-design.md),
[architecture](docs/architecture.md) and [USB protocol](docs/protocol.md).

## Preparing a public repository

Publish a clean snapshot of this application, rather than the surrounding workspace
or the working folder containing private files:

```powershell
python scripts/export_public.py --output artifacts/public-release
```

The exporter copies an explicit set of source directories, includes required
vendored sources and licenses, omits nested Git metadata, and excludes credentials,
the generated policy, flash dumps, toolchains and build products. It refuses to
overwrite an existing output and writes `PUBLICATION-MANIFEST.json` with file hashes.
Review the snapshot before initializing Git in that directory. The exporter is not
a general secret scanner and does not review Git history.

See [publication review](docs/publication-review.md) for the checks performed and
remaining licensing decisions. If publishing from an existing Git repository,
review its full history too: ignore rules do not remove previously committed data.

## Licensing and attribution

Dependency licenses and revision pins are recorded in
[third-party notices](docs/third-party-notices.md). Preserve those notices and the
upstream license files when redistributing the sources.

A license for the original project code has **not yet been selected**. No blanket
project license is asserted by this README. Select and add the intended license
before presenting the repository as open-source; copied assets with unclear
provenance also need resolution as described in the publication review.

