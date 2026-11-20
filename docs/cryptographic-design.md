# Cryptographic design and limits

## Statement and inputs

The witness contains a uniformly generated six-element BabyBear secret, ten sibling digests,
and ten private direction bits. A fixed-depth (1,024-slot) registry commits to H(secret).
The AIR computes that commitment, follows exactly ten private Merkle directions to the trusted
public root, computes a context-specific nullifier, and binds the requested operation.
The local registry enrolls four credentials; the remaining slots are random filler digests with
no retained preimages. The practical anonymity set is at most those four enrolled members, not
1,024 operators.

Public STARK inputs are thirty canonical BabyBear elements (120 bytes), in this order:

| Elements | Meaning |
| --- | --- |
| 0..6 | trusted registry root |
| 6..12 | nullifier = Poseidon2(secret, scope) |
| 12..18 | operation digest derived from the complete context |
| 18..24 | Poseidon2(scope, operation digest) |
| 24..30 | scope derived from the complete context |

The device reconstructs the expected 128-byte context from its own state:

| Offset / bytes | Value |
| --- | --- |
| 0 / 24 | canonical registry root |
| 24 / 8 | reserved, zero |
| 32 / 32 | fresh device-generated challenge |
| 64 / 16 | device identifier: MAC followed by zeros |
| 80 / 16 | fresh boot nonce |
| 96 / 4 | policy epoch, LE u32 |
| 100 / 4 | request ID, LE u32 |
| 104 / 4 | operation ID, LE u32 |
| 108 / 4 | configuration argument, LE u32 |
| 112 / 16 | fixed policy/protocol domain ZK-P3-ACCESS-V1! |

Operation and scope digests use BLAKE3 derive-key mode with separate domain labels and unbiased
XOF rejection sampling into BabyBear. The device compares the public root, operation digest
and scope with its own expected values. The STARK binds all public values through its transcript
and constraints. A host-supplied “valid” bit has no authorization role.

Registry and nullifier hashing retain zkmcu's fixed-input Poseidon2-BabyBear width-16
permutation, alpha=7, 8 external and 13 internal rounds, six-element digests. Leaf, node and
nullifier use the upstream input conventions; they are not a general variable-length hash API.
The custom AIR, those conventions and their domain separation should receive independent
review before production enrollment or arbitrary attacker-chosen registries are supported.
BLAKE3-256 is used for STARK commitments and Fiat-Shamir, not as a replacement for verification.

## Hiding configuration

The selected PCS is HidingFriPcs, with ZK=true; plain TwoAdicFriPcs is not accepted by a fallback.
Both the trace/quotient and FRI commitment layers use MerkleTreeHidingMmcs with eight random
BabyBear salt elements per leaf (~247 bits of salt entropy). Four random codewords, interleaved
random trace rows, randomized quotient chunks and the upstream random FRI batching polynomial
are enabled by the established implementation.

Three independent 256-bit OS-generated seeds initialize ChaCha20: trace salts, FRI salts and PCS
masking. No fixed seed, SmallRng, witness-derived seed or copied RNG state is used for proving.
A verifier instantiates the same types with fixed unused seeds: verification never generates
salts or masks and does not depend on their values.

There are 256 real trace rows and 256 random rows, rather than the reference's 16-row non-hiding
trace. With binary folding and 64 queries, this leaves masking headroom beyond the queried base
field evaluations and the extension-field out-of-domain openings. This choice must be reviewed
together with Plonky3's complete leakage bound; merely changing proof bytes between runs is not
a proof of zero knowledge.

Upstream describes part of its ZK randomization as statistical, not perfect ZK. This project
uses that mechanism, does not upgrade it to a perfect/unconditional guarantee, and has no
independent simulator proof for the complete application. The original non-hiding configuration
would expose constant witness columns; it is not offered as a production compatibility mode.
See [HidingFriPcs](https://github.com/Niek-Kamer/Plonky3/blob/6ffc1fbe46637dd5d62a6b3f423546a4c04b12d6/fri/src/hiding_pcs.rs)
and [salted commitments](https://github.com/Niek-Kamer/Plonky3/blob/6ffc1fbe46637dd5d62a6b3f423546a4c04b12d6/merkle-tree/src/hiding_mmcs.rs).

## Fixed security parameters

BabyBear p = 2^31 - 2^27 + 1; quartic extension; 256 real rows; 330 trace columns
(the layout's size is authoritative); log_blowup=2; 64 queries; binary FRI folding;
final polynomial length 1; commit grinding 16 bits and query grinding 17 bits.
The 64 queries and grinding counts are retained from zkmcu; blowup increases from 2 to 4 for
the hiding configuration. The verifier config is compiled in and requires degree_bits=9;
the proof never chooses the security policy.

FRI conjectures, field-size limits, algebraic soundness, Fiat-Shamir assumptions, cryptographic
hash security and custom AIR correctness all matter. There is no claim of a proven 128-bit
overall bound. Six BabyBear digest elements provide ~185.4 bits, hence at most ~92.7 bits of
generic classical collision resistance. Increasing PoW does not repair this registry-hash limit.

## Replay, revocation and privacy

Only one outstanding challenge exists. It is consumed before invoking crypto. Expiry is checked
before and after verification; proof transfer has a 3-second idle limit. Reset changes the boot
nonce. Reusing proof bytes with a new nonce, operation, argument, device, boot or policy fails.
Nullifiers change with the challenge-specific scope; no persistent cross-session nullifier is
retained. Primary replay protection is the device's one-use challenge, not a permanent operator
identifier. Repeated identical context would yield the same nullifier, so entropy quality matters.
The firmware temporarily enables ESP-IDF's SAR-ADC entropy source around RNG reads; RF and ADC
applications must coordinate that source if added later.
[ESP-IDF RNG prerequisites](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/system/random.html).

Registry administration is trusted. Revocation replaces a leaf, increments the epoch, refreshes
remaining private paths and installs the new root/epoch in firmware. A registry file alone does
not update the board. Physical reflashing can also restore an old policy; rollback protection
and authenticated live policy updates are not implemented.

No private secret, index or sibling is sent over USB. The local prover knows its credential and
path. USB observers see operations, device identifiers, timing and context-specific nullifiers;
host compromise, traffic analysis, live proof relaying and physical device compromise are outside
the anonymity guarantee. Credential files and backups are not encrypted at rest.

## Post-quantum analysis and roadmap

There are no elliptic-curve or pairing assumptions in the selected proof. This does not establish
post-quantum security. Generic quantum preimage search, quantum collision algorithms, quantum
Fiat-Shamir analysis and algebraic attacks on the chosen Poseidon2 instance must be considered.
For an approximately 185-bit digest, idealized quantum collision work can be around 2^(185/3),
under the algorithm's memory/model assumptions; this is far from a blanket “128-bit PQ” claim.
BLAKE3-256 commitments alone do not strengthen the smaller credential digest.

ML-DSA is a candidate for authenticated registry updates, with version/epoch and anti-rollback
state included in the signed message. ML-KEM would need peer authentication, key confirmation,
a KDF, AEAD and session binding; KEM alone is not authenticated transport.
Espressif's esp-pqc component offers evaluation paths, but compatibility, memory cost and
integration with this ESP-IDF build have not been validated. No ML-KEM, ML-DSA, Secure Boot
or irreversible security setting is enabled.
[Espressif's component overview](https://developer.espressif.com/blog/2026/10/esp32-post-quantum-cryptography/).

