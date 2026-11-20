# USB protocol version 1

Frames use little-endian integers:

| Bytes | Field |
| --- | --- |
| 0..4 | ASCII ZKAC |
| 4 | version = 1 |
| 5 | message type; response sets bit 7 |
| 6..8 | payload length u16, at most 1,024 |
| 8..12 | request ID u32 |
| 12.. | payload |
| final 4 | IEEE CRC-32 over header + payload |

CRC is not authorization. Header/version/size errors discard the pending authorization.
A partial frame expires after 2 seconds idle or 10 seconds total. Noise is scanned for a new
magic prefix, with bounded buffers.

| Type | Request payload | Response |
| --- | --- | --- |
| 1 HELLO | empty | seven u32: version, max proof, chunk bytes, challenge TTL ms, maintenance TTL ms, ready, epoch |
| 2 REQUEST | operation u32, argument u32 | 128-byte context + TTL u32; or result on denial |
| 3 BEGIN | proof size u32 + 120 public-input bytes | code u32 + next offset u32 |
| 4 CHUNK | exact next offset u32 + 1..1020 bytes | code u32 + next offset u32 |
| 5 FINISH | empty | result after actual local STARK verification |
| 6 ABORT | empty | restricted result; drops proof/challenge/maintenance |
| 7 STATUS | empty | public result, with protected configuration redacted |
| 8 DIRECT | any | denied; no unproved maintenance command exists |

Proofs are at most 524,288 bytes. BEGIN must have exactly 124 bytes. Only one transfer exists.
The challenge expires in 60 seconds, transfer idle timeout is 3 seconds, maintenance lease is
30 seconds. CHUNK cannot repeat, skip, wrap or exceed the declared proof size. FINISH requires
all bytes and consumes the challenge before verification. Context and expiry are checked
against device state, and expiry/maintenance conditions are checked again after verification.

Result payload is 22 u32 (88 bytes), ordered as:

code, operation, protected configuration (accepted result only), maintenance, accepted,
successful verifications, rejections, proof bytes, verify microseconds, free heap,
minimum free heap, Rust live-payload peak, main stack free bytes, receive microseconds,
authorization microseconds, selected touch operation, LCD healthy, LCD frames,
internal free heap, PSRAM free, touch present, last render microseconds.

Codes: 0 OK, 1 INVALID, 2 EXPIRED, 3 REPLAY, 4 FRAMING, 5 BUSY (reserved),
6 UNAVAILABLE, 7 POLICY (reserved), 8 OPERATION, 9 MEMORY.
An expired transfer can emit an unsolicited FINISH result for its request ID. Host clients
must discard unrelated IDs and never interpret an ACK as authorization.

