"""Local sensors, independent retry and per-field freshness; never demo data."""
import time
from scd41 import SCD41
from bme280_periodic import PeriodicBME280

METRICS = ('co2', 'temperature', 'humidity', 'pressure')
LIMITS = {'co2': (1, 65535), 'temperature': (-40, 85),
          'humidity': (0, 100), 'pressure': (300, 1100)}


def create_i2c():
    from machine import SoftI2C, Pin
    # SoftI2C has an explicit clock stretching timeout in microseconds.
    return SoftI2C(sda=Pin(8), scl=Pin(9), freq=100000, timeout=2000)


class SensorSource:
    def __init__(self, bus_factory=create_i2c):
        self.bus_factory = bus_factory
        self.bus = None
        self.bus_due = None
        self.turn = 0
        self.factories = {'scd41': SCD41, 'bme280': PeriodicBME280}
        self.slots = {name: {'driver': None, 'due': None, 'sample': None,
                            'at': None, 'error': None} for name in self.factories}

    def poll(self, now):
        if self.bus is None:
            if self.bus_due is not None and time.ticks_diff(now, self.bus_due) < 0:
                return
            try:
                self.bus = self.bus_factory()
            except (OSError, ValueError, RuntimeError) as error:
                self.bus_due = time.ticks_add(now, 10000)
                for slot in self.slots.values(): slot['error'] = type(error).__name__
            return
        name = ('scd41', 'bme280')[self.turn]
        self.turn = 1-self.turn
        slot = self.slots[name]
        if slot['due'] is not None and time.ticks_diff(now, slot['due']) < 0:
            return
        try:
            if slot['driver'] is None:
                slot['driver'] = self.factories[name](self.bus)
                slot['started'] = now
            sample = slot['driver'].poll(now)
            if sample is not None:
                for key, value in sample.items():
                    low, high = LIMITS[key]
                    if type(value) not in (int, float) or not low <= value <= high:
                        raise ValueError('Invalid '+key)
                slot.update(sample=sample, at=now, error=None)
            else:
                reference = slot['at']
                if reference is None or time.ticks_diff(slot['started'], reference) > 0:
                    reference = slot['started']
                if time.ticks_diff(now, reference) > 20000:
                    raise ValueError('Sensor sample timeout')
        except (OSError, ValueError, RuntimeError) as error:
            # Drop current sample immediately; keep last-good only for diagnostics.
            slot['driver'] = None
            slot['error'] = type(error).__name__ + ': ' + str(error)
            slot['due'] = time.ticks_add(now, 10000)

    def snapshot(self, now):
        data = {key: None for key in METRICS}
        data.update(demo=False, sources={}, field_age_ms={}, sensors={})
        available = {}
        for name, slot in self.slots.items():
            age = None if slot['at'] is None else max(0, time.ticks_diff(now, slot['at']))
            state = ('error' if slot['error'] else 'warming' if age is None else
                     'stale' if age > 15000 else 'ok')
            available[name] = state == 'ok'
            data['sensors'][name] = {'state': state, 'age_ms': age, 'error': slot['error']}
        for key in METRICS:
            candidates = ('scd41',) if key == 'co2' else ('bme280',) if key == 'pressure' else ('bme280', 'scd41')
            for name in candidates:
                if available[name]:
                    data[key] = self.slots[name]['sample'][key]
                    data['sources'][key] = name
                    data['field_age_ms'][key] = data['sensors'][name]['age_ms']
                    break
            else:
                data['sources'][key] = None
                data['field_age_ms'][key] = None
        data['sensor_caption'] = ('SENSORES OK' if all(available.values()) else 'SENSORES: REVISAR')
        return data
