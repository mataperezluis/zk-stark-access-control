# Threat model

Protected assets are credential secrets, membership position, trusted root/epoch, one-use
challenges and the maintenance command boundary. The USB host is untrusted for authorization:
it may change every frame, public input and proof byte. The registry administrator, correct
firmware, entropy source, prover environment and underlying cryptographic implementation are
trusted.

All access begins restricted. A valid operation-specific local STARK is necessary for each
privileged operation. Failure clears the maintenance lease. Challenge consumption precedes
verification and a second expiry check precedes execution. Public status omits the protected
configuration value. Touch only selects a request; no UI callback executes the command.

Covered adversarial cases include invalid credentials/paths, root/epoch changes, modified
proofs/public inputs, challenge/operation rebinding, replay, expiration, malformed encoding,
oversized headers/proofs, missing/out-of-order chunks and unauthenticated direct commands.
Host cryptographic tests and real device tests are distinguished in their result files.

Resource bounds: 1,024-byte frames, 512 KiB proof cap, one PSRAM proof buffer, one pending
challenge and a 6 MiB Rust allocation budget. The parser validates lengths before allocation.
CRC-32 is corruption framing only. An attacker with USB access can still occupy the verifier,
force repeated expensive checks, cause allocation failure/panic resets with sufficiently
adversarial encodings, or interrupt communication. This implementation is not availability
hardened against a determined local attacker.

USB is not confidential or peer-authenticated. A live relay to a willing authorized prover
is not prevented. Physical attackers can replace firmware or roll policy back because secure
boot/flash encryption/eFuse protections are deliberately outside the task. Secrets stored on
the PC and original-program flash backups depend on filesystem/account protection.
This is a serious implementation starting point, with explicit research and deployment gaps,
not an audited production access controller.

