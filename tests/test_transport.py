import struct
import unittest
from prover.transport import Decoder, frame, MAX_PAYLOAD

class FramingTests(unittest.TestCase):
    def test_all_split_boundaries_and_concatenated_frames(self):
        expected = (2, 31, b"example")
        encoded = frame(*expected)
        for split in range(len(encoded)+1):
            decoder=Decoder()
            messages=decoder.feed(encoded[:split])+decoder.feed(encoded[split:])
            self.assertEqual(messages,[expected])
        self.assertEqual(Decoder().feed(encoded*2),[expected,expected])
    def test_corruption_noise_and_recovery(self):
        encoded=bytearray(frame(2,31,b"example"));encoded[-1]^=1
        good=frame(1,99,b"")
        self.assertEqual(Decoder().feed(b"boot noise"+encoded+good),[(1,99,b"")])
    def test_oversize_and_wrong_version_recover(self):
        bad=struct.pack("<4sBBHI",b"ZKAC",1,2,65535,5)
        good=frame(1,8)
        self.assertEqual(Decoder().feed(bad+good),[(1,8,b"")])
        with self.assertRaises(ValueError):frame(2,1,b"x"*(MAX_PAYLOAD+1))
    def test_partial_buffer_is_bounded(self):
        decoder=Decoder();decoder.feed(b"x"*100000)
        self.assertLessEqual(len(decoder.buffer),3)

if __name__=="__main__":unittest.main()

