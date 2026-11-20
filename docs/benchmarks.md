# Measured benchmarks and validation

Date: 2026-11-10T11:28:41.820639-03:00. Five real, fresh, authorized diagnostic requests over COM5.
ESP32-S3 rev 0.2, **160 MHz configured CPU**, DFS disabled,
8 MiB octal PSRAM at 40 MHz, 16 MiB flash, JD9853 rendering active on core 1.
The generic board's advertised 240 MHz is not the ESP-IDF configured frequency for these runs.
Host: Intel64 Family 6 Model 151 Stepping 2, GenuineIntel; Windows-10-10.0.26200-SP0; Python 3.11.7.
Rust prover is the release build, single threaded, without target-cpu=native overrides.

| Quantity | Real measurement |
| --- | --- |
| Local ESP32 verification, median | 1845.470 ms |
| USB proof transfer with framing/ACKs, median | 1105.110 ms |
| Host proof generation, median | 257.443 ms |
| Host self-verification, median | 3.980 ms |
| Total request → decision on host, median | 3292.214 ms |
| Proof size, range | 382,823–382,986 bytes |
| Rust verifier peak live payload on ESP32 | 543,232 bytes |
| Free 8-bit-capable heap after each request | 8,674,156 bytes |
| Historical minimum free heap | 7,591,268 bytes |
| Observed baseline minus historical minimum | 1,082,888 bytes |
| Main/verifier stack minimum free | 55,880 of 65,536 bytes |
| Main/verifier stack maximum observed use | 9,656 bytes |
| Internal heap free after verification | 289,100 bytes |
| PSRAM free after verification | 8,385,056 bytes |
| Last concurrent LCD frame wall time, median | 237.251 ms |
| Host prover additional tracked Rust heap peak | 5,458,824 bytes |
| Host verifier additional tracked Rust heap peak | 743,436 bytes |
| Firmware.bin file size | 441,008 bytes |

Firmware SHA-256: 9c16f721bf5c72b2b8c635d4d4a1902941c619439a54719d6d5f008c753f3388.
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
