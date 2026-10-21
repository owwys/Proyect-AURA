import sys, time, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'firmware'))
time.ticks_add = lambda a,b: (a+b) % (1<<30)
time.ticks_diff = lambda a,b: ((a-b+(1<<29)) % (1<<30))-(1<<29)
import scd41

class Bus:
    def __init__(self): self.commands=[]; self.reply=b''
    def writeto(self, address, data): self.commands.append(bytes(data)); return len(data)
    def readfrom(self, address, count): return self.reply

class SensorTests(unittest.TestCase):
    def test_crc_reference(self):
        self.assertEqual(scd41.crc8(bytes.fromhex('beef')), 0x92)

    def test_crc_every_word(self):
        frame=bytes.fromhex('01f4336667a25eb93c')
        self.assertEqual(scd41.decode_words(frame), [500,26215,24249])
        for i in (2,5,8):
            bad=bytearray(frame); bad[i]^=1
            with self.assertRaises(ValueError): scd41.decode_words(bad)

    def test_waits_do_not_read_early(self):
        bus=Bus(); driver=scd41.SCD41(bus)
        self.assertIsNone(driver.poll(0))
        self.assertEqual(bus.commands, [b'\x3f\x86'])
        driver.poll(499); self.assertEqual(len(bus.commands),1)
        driver.poll(500); self.assertEqual(bus.commands[-1],b'\x21\xb1')
        driver.poll(5499); self.assertEqual(len(bus.commands),2)
        driver.poll(5500); self.assertEqual(bus.commands[-1],b'\xe4\xb8')
        bus.reply=b'\x00\x01'+bytes([scd41.crc8(b'\x00\x01')])
        driver.poll(5501)
        driver.poll(5502); self.assertEqual(bus.commands[-1],b'\xec\x05')
        bus.reply=bytes.fromhex('01f4336667a25eb93c')
        sample=driver.poll(5503)
        self.assertEqual(sample['co2'],500)
        self.assertAlmostEqual(sample['temperature'],25.00267,places=4)

if __name__ == '__main__': unittest.main()
