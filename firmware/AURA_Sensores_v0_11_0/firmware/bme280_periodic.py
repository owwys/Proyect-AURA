"""Nonblocking forced conversions using bme280_float compensation.

Only the raw read is overridden; no sleep or conversion loop is called.
"""
import time
from bme280_float import BME280


class BufferedBME280(BME280):
    def read_raw_data(self, result):
        raw = self._l8_barray
        self.i2c.readfrom_mem_into(self.address, 0xf7, raw)
        pressure = ((raw[0] << 16) | (raw[1] << 8) | raw[2]) >> 4
        temperature = ((raw[3] << 16) | (raw[4] << 8) | raw[5]) >> 4
        humidity = (raw[6] << 8) | raw[7]
        if pressure == 0x80000 or temperature == 0x80000 or humidity == 0x8000:
            raise ValueError('BME280 skipped measurement')
        result[0], result[1], result[2] = temperature, pressure, humidity


class PeriodicBME280:
    def __init__(self, i2c):
        self.i2c = i2c
        self.driver = None
        self.state = 'identify'
        self.due = None

    def poll(self, now):
        if self.due is not None and time.ticks_diff(now, self.due) < 0:
            return None
        if self.state == 'identify':
            if self.i2c.readfrom_mem(0x76, 0xd0, 1) != b'\x60':
                raise ValueError('BME280 chip ID')
            self.state, delay = 'calibration_wait', 10
        elif self.state == 'calibration_wait':
            # NVM copy must finish before reading calibration coefficients.
            if self.i2c.readfrom_mem(0x76, 0xf3, 1)[0] & 1:
                raise ValueError('BME280 NVM busy')
            self.state, delay = 'init', 0
        elif self.state == 'init':
            self.driver = BufferedBME280(i2c=self.i2c, address=0x76, mode=1)
            if not self.driver.dig_T1 or not self.driver.dig_P1:
                raise ValueError('BME280 calibration')
            self.state, delay = 'humidity', 0
        elif self.state == 'humidity':
            self.i2c.writeto_mem(0x76, 0xf2, b'\x01')
            self.state, delay = 'trigger', 0
        elif self.state == 'trigger':
            self.i2c.writeto_mem(0x76, 0xf4, b'\x25')
            self.state, delay = 'status', 20  # x1 T/P/H: <10 ms conversion
            self.started = now
        elif self.state == 'status':
            if self.i2c.readfrom_mem(0x76, 0xf3, 1)[0] & 8:
                if time.ticks_diff(now, self.started) >= 200:
                    raise ValueError('BME280 conversion timeout')
                delay = 10
            else:
                self.state, delay = 'read', 0
        else:
            t, p, h = self.driver.read_compensated_data()
            self.state = 'humidity'
            self.due = time.ticks_add(now, 2000)
            return {'temperature': t, 'pressure': p/100, 'humidity': h}
        self.due = time.ticks_add(now, delay)
        return None
