# Architecture

The selected route uses zkmcu as the primary AIR/embedded architecture reference, Plonky3 as
the established STARK implementation, a no_std Rust static library, ESP-IDF C++ control and
rendering tasks, and a Python USB client. The PC produces proof bytes; only the device verifier
can return the cryptographic success that enables the command handler.

```mermaid
sequenceDiagram
  participant H as Python + Rust prover
  participant D as ESP32 command handler
  participant V as Local Rust verifier
  participant L as JD9853 task
  H->>D: operation + argument + request ID
  D->>H: fresh nonce + boot/device/root/epoch/policy context
  D->>L: CHALLENGE GENERATED
  H->>H: private credential + Merkle path; hiding STARK
  H->>D: public inputs + bounded proof chunks
  D->>D: consume outstanding challenge
  D->>L: VERIFYING STARK
  D->>V: proof + public inputs + reconstructed expected context
  V-->>D: cryptographic verdict
  D->>D: recheck expiry and execute exactly bound operation
  D->>L: actual result and maintenance state
  D-->>H: decision + real measurements
```

The main ESP-IDF task owns the USB parser, challenge lifecycle, proof buffer and maintenance
state. Its 64 KiB internal stack also runs the synchronous verifier. The display task is pinned
to core 1 with a 6 KiB stack and a 5,504-byte internal DMA stripe buffer. A spinlock protects
snapshot copies; atomic values publish touch selection, transfer health and rendering metrics.
No private credential or membership position is sent to the display.

Proof storage and Rust allocations use the physically verified 8 MB PSRAM. The Rust allocator
has a 6 MiB live-payload budget, preserves requested alignment, and reports its measured peak.
Malformed input that triggers a Rust panic or allocation failure aborts/reboots the device;
startup is restricted. This protects the authorization boundary but remains an availability
limitation. It is not claimed to be a crash-proof parser.

Operations are diagnostics (1), enter maintenance (2), set RAM configuration 0..100 (3),
and exit maintenance (4). Every operation executes at the handler boundary after a local STARK
success. Set additionally requires the earlier maintenance lease still to be valid. A proof is
single-use, not a session bearer token. Failure, timeout and abort close maintenance immediately.
The configuration value survives a failed proof, as a previously authorized setting, but the
maintenance capability does not. Reset restores the noncritical parameter to 25.

The touch menu selects an operation for the host's `--operation selected` command. It never
calls the executor. LCD failure prevents new authorization and is rechecked after verification.

## Reference investigation

Pinned zkmcu: `69b59e6b999ed69c5663878486f425cf8ed8fd14`.
Its `pq_semaphore.rs` provides the Poseidon2 membership/nullifier/scope AIR and no_std design.
Its `zkmcu-host-gen/src/pq_semaphore.rs` explicitly describes non-hiding TwoAdicFriPcs:
that configuration was not reused as a privacy guarantee.
[Source](https://github.com/Niek-Kamer/zkmcu/tree/69b59e6b999ed69c5663878486f425cf8ed8fd14).

The downloaded Niek-Kamer Plonky3 fork is pinned separately in `vendor/PLONKY3-PIN.txt`.
This is a newer revision than zkmcu's original gitlink, so API/target compatibility was tested,
not assumed. The AIR adaptation is reproducible with `scripts/adapt_zkmcu.py`.
Local changes enforce a non-skippable leaf → ten hops → nullifier → scope → padding schedule,
bind scope as a public value, and use 256 real rows for masking headroom.

The HidingFriPcs wrapper requires both input and FRI MMCSs to hide; both are explicitly
MerkleTreeHidingMmcs here. Upstream examples use a non-cryptographic SmallRng with a warning;
this project uses independently OS-seeded ChaCha20 streams instead.
[Plonky3](https://github.com/Plonky3/Plonky3).

The Cargo workspace contains only the active host proof package and its embedded
static library. The zkmcu source subset retains the membership AIR, the host proof
reference, design notes and upstream licenses; unrelated applications
and benchmarks are not part of this project.

