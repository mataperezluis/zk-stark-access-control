"""Generate documentation only from saved real measurements."""
import json
from pathlib import Path
import statistics
root=Path(__file__).resolve().parents[1]
report=json.loads((root/"docs/benchmark-results.json").read_text())
samples=report["samples"];summary=report["summary"]
baseline=max(s["free_heap"] for s in samples)
minimum=min(s["minimum_free_heap"] for s in samples)
median=lambda key:statistics.median(s[key] for s in samples)
host_median=lambda key:statistics.median(s["host"][key] for s in samples)
text=f"""# Measured benchmarks and validation

Date: {report['date']}. Five real, fresh, authorized diagnostic requests over COM5.
ESP32-S3 rev 0.2, **{report['device']['cpu_mhz']} MHz configured CPU**, DFS disabled,
8 MiB octal PSRAM at 40 MHz, 16 MiB flash, JD9853 rendering active on core 1.
The generic board's advertised 240 MHz is not the ESP-IDF configured frequency for these runs.
Host: {report['host']['processor']}; {report['host']['platform']}; Python {report['host']['python']}.
Rust prover is the release build, single threaded, without target-cpu=native overrides.

| Quantity | Real measurement |
| --- | --- |
| Local ESP32 verification, median | {summary['median_verify_ms']:.3f} ms |
| USB proof transfer with framing/ACKs, median | {summary['median_transfer_ms']:.3f} ms |
| Host proof generation, median | {summary['median_host_generation_ms']:.3f} ms |
| Host self-verification, median | {host_median('self_verify_ms'):.3f} ms |
| Total request → decision on host, median | {summary['median_total_ms']:.3f} ms |
| Proof size, range | {summary['min_proof_bytes']:,}–{summary['max_proof_bytes']:,} bytes |
| Rust verifier peak live payload on ESP32 | {int(median('rust_peak_bytes')):,} bytes |
| Free 8-bit-capable heap after each request | {baseline:,} bytes |
| Historical minimum free heap | {minimum:,} bytes |
| Observed baseline minus historical minimum | {baseline-minimum:,} bytes |
| Main/verifier stack minimum free | {int(median('stack_free_bytes')):,} of 65,536 bytes |
| Main/verifier stack maximum observed use | {65536-int(median('stack_free_bytes')):,} bytes |
| Internal heap free after verification | {int(median('internal_free_heap')):,} bytes |
| PSRAM free after verification | {int(median('psram_free')):,} bytes |
| Last concurrent LCD frame wall time, median | {median('render_us')/1000:.3f} ms |
| Host prover additional tracked Rust heap peak | {int(host_median('prover_additional_heap_peak')):,} bytes |
| Host verifier additional tracked Rust heap peak | {int(host_median('verifier_additional_heap_peak')):,} bytes |
| Firmware.bin file size | {report['firmware_bytes']:,} bytes |

Firmware SHA-256: {report['firmware_sha256']}.
Raw reproducible values are in [benchmark-results.json](benchmark-results.json).

## Measurement boundaries

ESP32 verify_us brackets only the local C-ABI Rust verifier call. It includes strict public-context
checking, proof parsing and cryptographic verification; proof reception and UI rendering are not
inside that interval. Rendering runs concurrently, so normal CPU/cache/PSRAM contention remains
part of measured device wall time. The separate render_us includes rasterization, SPI transfer
and completion waits for a full frame; it must not be added to verification time as serial work.

receive_us starts at BEGIN and ends at FINISH, including chunk headers and ACK waits. The host
transfer timer ends after the last chunk ACK. Total host latency also includes request/reply,
process startup, proving and host self-check. Device authorization_us starts at REQUEST.
No UART baud-rate calculation substitutes for measured USB Serial/JTAG transport time.

Rust peak tracks live requested allocation payload, excluding allocator headers, PSRAM proof
storage and task stacks. The historical heap minimum is an ESP-IDF heap statistic, not a
cycle-exact per-call process RSS measurement. Baseline-minus-minimum is an observed memory
pressure indicator, not an allocator-independent proof of exact peak simultaneous use.
Host allocator numbers likewise count Rust allocations, not total Windows process RSS.
All five successful requests returned heap to the same baseline.

## Validation evidence

- Native Rust: eight security tests passed, including real membership proofs, public-input/proof
  changes, root/operation/challenge binding, hiding randomization, mandatory random commitment,
  exact trace size and an attempted all-padding selector bypass.
- Python: four frame-codec tests passed.
- Integration: 17 test groups passed; 16 exercise the real board and one explicitly checks local
  rejection of invalid credential/path/stale epoch before proving. All four maintenance operations
  ran; diagnostics observed configuration change from 25 to 42; expiry and failures closed access.
- Real policy rotation: an old root/epoch proof was rejected after an epoch-2 reflash, a remaining
  member's refreshed witness was accepted, and the initial policy was restored and tested.
- LCD: healthy SPI transfers and advancing frame counters were observed; AXS5106 I2C probe
  succeeded. Human visual/touch-coordinate confirmation remains outstanding.
- Original project: SHA-256 checks of 226 original files reported unchanged.

See [device-test-results.json](device-test-results.json),
[policy-lifecycle-results.json](policy-lifecycle-results.json),
[host-test-results.txt](host-test-results.txt) and [isolation-result.json](isolation-result.json).
The long expiry tests use the actual 60-second challenge and 30-second maintenance deadlines.
The integration run preceded a display-label correction; the final firmware was recompiled,
flashed and exercised by policy rotation and these five benchmark requests.

## Reproduce

From the isolated project root:

```powershell
python -m scripts.benchmark --port COM5 --count 5
python scripts/write_benchmark_report.py
```

No ARM/RISC-V zkmcu measurements are presented as ESP32 results. No numbers are simulated.
Remaining work includes an independent AIR/hiding-configuration audit, broader malformed-proof
fuzzing/resource-exhaustion hardening, physical UI confirmation and stronger production security
parameters. See the explicit ~92.7-bit credential-digest collision ceiling in the design document.
"""
(root/"docs/benchmarks.md").write_text(text,encoding="utf-8")
print(json.dumps(summary,indent=2))

