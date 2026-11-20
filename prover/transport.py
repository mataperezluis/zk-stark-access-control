"""Bounded version-1 USB framing. CRC detects corruption; it is not authentication."""
import secrets
import struct
import time
import zlib

MAGIC = b"ZKAC"
HEADER = struct.Struct("<4sBBHI")
MAX_PAYLOAD = 1024
MAX_PROOF = 524288
HELLO, REQUEST, BEGIN, CHUNK, FINISH, ABORT, STATUS, DIRECT = range(1, 9)
POLICY_ID = b"ZK-P3-ACCESS-V1!"
FIELDS = ("code", "operation", "configuration", "maintenance", "accepted", "successes",
          "rejected", "proof_bytes", "verify_us", "free_heap", "minimum_free_heap",
          "rust_peak_bytes", "stack_free_bytes", "receive_us", "authorization_us",
          "selected_operation", "lcd_healthy", "lcd_frames", "internal_free_heap", "psram_free",
          "touch_present", "render_us")
CODES = ("OK", "INVALID_PROOF", "EXPIRED", "REPLAY", "FRAMING", "BUSY",
         "UNAVAILABLE", "POLICY", "OPERATION", "MEMORY")

class Denied(RuntimeError):
    def __init__(self, result):
        self.result = result
        code = result.get("code", 1)
        super().__init__(CODES[code] if 0 <= code < len(CODES) else "UNKNOWN")

def frame(kind, request_id, payload=b""):
    if len(payload) > MAX_PAYLOAD or not 0 <= request_id <= 0xffffffff:
        raise ValueError("frame limits")
    body = HEADER.pack(MAGIC, 1, kind, len(payload), request_id) + payload
    return body + struct.pack("<I", zlib.crc32(body))

def result(payload):
    if len(payload) != 88:
        raise ValueError("result size")
    return dict(zip(FIELDS, struct.unpack("<22I", payload)))

class Decoder:
    def __init__(self):
        self.buffer = bytearray()
    def feed(self, data):
        self.buffer.extend(data)
        messages = []
        while True:
            at = self.buffer.find(MAGIC)
            if at < 0:
                self.buffer[:] = self.buffer[-3:]
                break
            del self.buffer[:at]
            if len(self.buffer) < HEADER.size:
                break
            _, version, kind, length, ident = HEADER.unpack_from(self.buffer)
            if version != 1 or length > MAX_PAYLOAD:
                del self.buffer[0]
                continue
            total = HEADER.size + length + 4
            if len(self.buffer) < total:
                break
            body = self.buffer[:HEADER.size + length]
            crc = struct.unpack_from("<I", self.buffer, HEADER.size + length)[0]
            if zlib.crc32(body) == crc:
                messages.append((kind, ident, bytes(body[HEADER.size:])))
                del self.buffer[:total]
            else:
                del self.buffer[0]
        return messages

class Client:
    def __init__(self, port, timeout=90):
        import serial
        self.serial = serial.Serial(port=None, baudrate=115200, timeout=0.1, write_timeout=3)
        self.serial.dtr = False
        self.serial.rts = False
        self.serial.port = port
        self.serial.open()
        self.decoder = Decoder()
        self.messages = []
        self.timeout = timeout
    def close(self):
        self.serial.close()
    def send(self, kind, ident, payload=b""):
        encoded = frame(kind, ident, payload)
        if self.serial.write(encoded) != len(encoded):
            raise IOError("interrupted USB write")
    def receive(self, kind, ident, timeout=None):
        deadline = time.monotonic() + (self.timeout if timeout is None else timeout)
        while time.monotonic() < deadline:
            while self.messages:
                got_kind, got_id, payload = self.messages.pop(0)
                if got_id != ident:
                    continue
                if got_kind == kind | 0x80:
                    return payload
                if got_kind == FINISH | 0x80 and len(payload) == 88:
                    raise Denied(result(payload))
            first = self.serial.read(1)
            if first:
                first += self.serial.read(min(self.serial.in_waiting, 4096))
                self.messages.extend(self.decoder.feed(first))
        raise TimeoutError("USB response timeout")
    def exchange(self, kind, ident, payload=b"", timeout=None):
        self.send(kind, ident, payload)
        return self.receive(kind, ident, timeout)
    def info(self):
        payload = self.exchange(HELLO, secrets.randbits(32))
        if len(payload) != 28:
            raise ValueError("capability encoding")
        return dict(zip(("version", "max_proof", "chunk_bytes", "challenge_ttl_ms",
                         "maintenance_ttl_ms", "ready", "policy_epoch"), struct.unpack("<7I", payload)))
    def status(self):
        return result(self.exchange(STATUS, secrets.randbits(32)))
    def request(self, operation, argument=0):
        ident = secrets.randbits(32) or 1
        payload = self.exchange(REQUEST, ident, struct.pack("<II", operation, argument))
        if len(payload) == 88:
            raise Denied(result(payload))
        if len(payload) != 132 or payload[112:128] != POLICY_ID:
            raise ValueError("challenge encoding")
        return ident, payload[:128], struct.unpack_from("<I", payload, 128)[0]
    def begin(self, ident, size, public):
        ack = self.exchange(BEGIN, ident, struct.pack("<I", size) + public)
        if len(ack) == 88:
            raise Denied(result(ack))
        if len(ack) != 8 or struct.unpack("<II", ack) != (0, 0):
            raise ValueError("begin ACK")
    def upload(self, ident, proof, public):
        if not 0 < len(proof) <= MAX_PROOF or len(public) != 120:
            raise ValueError("proof/public limits")
        start = time.perf_counter()
        self.begin(ident, len(proof), public)
        for offset in range(0, len(proof), MAX_PAYLOAD - 4):
            part = proof[offset:offset + MAX_PAYLOAD - 4]
            ack = self.exchange(CHUNK, ident, struct.pack("<I", offset) + part)
            if len(ack) == 88:
                raise Denied(result(ack))
            if len(ack) != 8 or struct.unpack("<II", ack) != (0, offset + len(part)):
                raise ValueError("chunk ACK")
        transfer_ms = (time.perf_counter() - start) * 1000
        response = result(self.exchange(FINISH, ident))
        response["host_transfer_ms"] = round(transfer_ms, 3)
        return response

