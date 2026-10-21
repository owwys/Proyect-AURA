"""SCD4x periodic mode; each poll advances at most one I2C operation.

Sensirion SCD4x datasheet v1.7, sections 3.6, 3.9.2 and 3.12.
No forced recalibration, EEPROM writes or changes to ASC/offset.
"""
import time


def crc8(data):
    crc = 0xff
    for value in data:
        crc ^= value
        for _ in range(8):
            crc = ((crc << 1) ^ (0x31 if crc & 0x80 else 0)) & 0xff
    return crc


def decode_words(data):
    if not data or len(data) % 3:
        raise ValueError('SCD41 length')
    words = []
    for i in range(0, len(data), 3):
        if crc8(data[i:i+2]) != data[i+2]:
            raise ValueError('SCD41 CRC')
        words.append((data[i] << 8) | data[i+1])
    return words


class SCD41:
    def __init__(self, i2c):
        self.i2c = i2c
        self.state = 'stop'
        self.due = None

    def _command(self, value):
        self.i2c.writeto(0x62, bytes((value >> 8, value & 255)))

    def poll(self, now):
        if self.due is not None and time.ticks_diff(now, self.due) < 0:
            return None
        if self.state == 'stop':
            self._command(0x3f86)
            self.state, delay = 'start', 500
        elif self.state == 'start':
            self._command(0x21b1)
            self.state, delay = 'ready_command', 5000
        elif self.state == 'ready_command':
            self._command(0xe4b8)
            self.state, delay = 'ready_read', 1
        elif self.state == 'ready_read':
            raw = self.i2c.readfrom(0x62, 3)
            if len(raw) != 3:
                raise ValueError('SCD41 length')
            ready = decode_words(raw)[0] & 0x7ff
            self.state, delay = ('measure_command', 0) if ready else ('ready_command', 1000)
        elif self.state == 'measure_command':
            self._command(0xec05)
            self.state, delay = 'measure_read', 1
        else:
            raw = self.i2c.readfrom(0x62, 9)
            if len(raw) != 9:
                raise ValueError('SCD41 length')
            co2, temperature, humidity = decode_words(raw)
            if co2 == 0:
                raise ValueError('SCD41 invalid CO2')
            self.state = 'ready_command'
            self.due = time.ticks_add(now, 5000)
            return {'co2': co2, 'temperature': -45+175*temperature/65535,
                    'humidity': 100*humidity/65535}
        self.due = time.ticks_add(now, delay)
        return None
