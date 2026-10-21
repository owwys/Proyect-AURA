"""Pruebas en ordenador: python3 -m unittest discover -s tests -v."""
import sys
import time
import types
import struct
sys.modules['micropython'] = types.SimpleNamespace(const=lambda value: value)
sys.modules['ustruct'] = struct
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'firmware'))


class FrameBuffer:
    def __init__(self, buffer, width, height, fmt):
        self.buffer, self.width, self.height = buffer, width, height
        self.fmt = fmt
        self.points = {}

    def fill(self, color):
        self.fill_rect(0, 0, self.width, self.height, color)
        self.points.clear()

    def fill_rect(self, x, y, w, h, color):
        assert w > 0 and h > 0
        assert 0 <= x < self.width and 0 <= y < self.height, (x, y)
        assert x + w <= self.width and y + h <= self.height, (x, y, w, h)

    def hline(self, x, y, w, color):
        self.fill_rect(x, y, w, 1, color)

    def text(self, text, x, y, color):
        self.fill_rect(x, y, len(text) * 8, 8, color)
        # Glifo lleno: exige que incluso el ultimo pixel escalado quepa.
        if self.fmt == 1:
            self.points = {(gx, gy): 1 for gx in range(8) for gy in range(8)}

    def pixel(self, x, y, color=None):
        assert 0 <= x < self.width and 0 <= y < self.height, (x, y)
        if color is None:
            return self.points.get((x, y), 0)
        offset = (y * self.width + x) * 2
        self.buffer[offset:offset + 2] = color.to_bytes(2, sys.byteorder)


class Pin:
    OUT = 1
    IN = 0
    PULL_UP = 2
    def __init__(self, number, mode=None, pull=None, value=0):
        self.number, self.current = number, (1 if pull == self.PULL_UP else value)
    def value(self, value=None):
        if value is None:
            return self.current
        self.current = value


class SPI:
    def __init__(self, *args, **kwargs):
        self.writes = []
        self.closed = False
    def init(self, **kwargs):
        self.last_init = kwargs
    def write_readinto(self, tx, rx):
        raw = 1000 if tx[0] == 0xD0 else 2000
        packed = raw << 3
        rx[:] = bytes((0, packed >> 8, packed & 255))
    def write(self, data):
        self.writes.append(bytes(data))
    def deinit(self):
        self.closed = True


sys.modules['framebuf'] = types.SimpleNamespace(FrameBuffer=FrameBuffer,
                                               RGB565=2, MONO_HLSB=1)
def no_i2c(**kwargs): raise OSError(19)
sys.modules['machine'] = types.SimpleNamespace(Pin=Pin, SPI=SPI, SoftI2C=no_i2c)
time.sleep_ms = lambda ms: None
time.ticks_add = lambda a, b: (a+b) % (1<<30)
from ili9341 import Display, rgb565
from demo import DemoSource, SCENARIOS, co2_style
from ui import Dashboard


class FirmwareTests(unittest.TestCase):
    def test_footer_shows_firmware_version_instead_of_counter(self):
        from ui import FIRMWARE_VERSION
        d = Display()
        ui = Dashboard(d)
        with patch.object(ui.g, 'text', wraps=ui.g.text) as text:
            ui.draw(DemoSource().read(), 1234)
        footer = [c.args for c in text.call_args_list if c.args[2] == 230]
        self.assertEqual([c[0] for c in footer],
                     ['DEMO / SIN WIFI', FIRMWARE_VERSION[:8]])
        self.assertEqual(footer[1][1] + ui.g.measure(footer[1][0]), 312)

    def test_network_captions_fit_and_clock_hidden_until_sync(self):
        d = Display()
        ui = Dashboard(d)
        for caption in ('SIN WIFI', 'WIFI...', 'WIFI OFF',
                        'WIFI OFF / RTC OK', 'WIFI OK / SIN HORA',
                        'WIFI OK / NTP OK', 'WIFI OK / RTC OK'):
            with patch('ui.local_clock.localtime') as clock, \
                 patch.object(ui.g, 'text', wraps=ui.g.text) as text:
                ui.draw(DemoSource().read(), 0, caption, False)
                clock.assert_not_called()
                self.assertTrue(any(c.args[0] == '--:--' for c in text.call_args_list))

    def test_arc_gap_symmetry_and_compact_numbers(self):
        from widgets import Widgets
        d = Display()
        w = Widgets(d.fb)
        points = set()
        for x, y, width in w.arc_spans:
            self.assertGreater(width, 0)
            for dx in range(width):
                points.add((x + dx, y))
        self.assertIn((120, 59), points)
        self.assertNotIn((120, 220), points)
        for x, y in points:
            self.assertIn((240-x, y), points)
        ui = Dashboard(d)
        self.assertLessEqual(ui.g.measure('9999', 4), 128)
        for co2 in (650, 950, 1650, 9999):
            data = DemoSource().read()
            data['co2'] = co2
            ui.draw(data, 0, 'WIFI OK / SIN HORA', False)

    def test_clock_format_and_unset(self):
        from ui import clock_text
        for hour, minute, expected in ((0, 0, '00:00'), (9, 5, '09:05'),
                                       (23, 59, '23:59')):
            self.assertEqual(clock_text((2026, 10, 15, hour, minute, 0, 3, 288)), expected)
        self.assertEqual(clock_text((2000, 1, 1, 0, 0, 0, 5, 1)), '--:--')
        with patch('ui.local_clock.localtime', return_value=(2026, 10, 15, 21, 8, 0, 3, 288)):
            self.assertEqual(clock_text(), '21:08')

    def test_face_and_reason_reflect_environment(self):
        from tft_environment import assess
        for co2 in (650, 1200, 1650):
            ui = Dashboard(Display())
            data = dict(co2=co2, temperature=22, humidity=40, pressure=1013)
            with patch.object(ui, '_face', wraps=ui._face) as face, patch.object(ui.g, 'text', wraps=ui.g.text) as text:
                ui.draw(data, 0)
            state, reason = assess(data)
            self.assertEqual(face.call_args.args[0], state)
            self.assertTrue(any(c.args[0] == reason for c in text.call_args_list))

    def test_clock_does_not_overlap_title(self):
        from graphics import Graphics
        g = Graphics(Display().fb)
        self.assertGreaterEqual(216, 8 + g.measure('AURA One') + 8)
        self.assertLessEqual(216 + g.measure('23:59'), 272 - 8)

    def test_retro_measurement_and_number_limits(self):
        from graphics import Graphics
        g = Graphics(Display().fb)
        self.assertEqual(g.measure('AURA', 1), 32)
        self.assertEqual(g.measure('AURA', 2), 64)
        self.assertEqual(g.measure('100', 2), 48)
        with self.assertRaises(ValueError):
            g.number(10000, 86, 1)
        with self.assertRaises(ValueError):
            g.text('A', 0, 0, 1, 0)

    def test_wire_color_bytes(self):
        for rgb, expected in [((255, 0, 0), b'\xf8\x00'),
                              ((0, 255, 0), b'\x07\xe0'),
                              ((0, 0, 255), b'\x00\x1f'),
                              ((255, 255, 255), b'\xff\xff')]:
            self.assertEqual(rgb565(*rgb).to_bytes(2, sys.byteorder), expected)

    def test_window_and_frame_transfer(self):
        d = Display()
        self.assertEqual(len(d.buffer), 153600)
        d.spi.writes.clear()
        d.fb.pixel(0, 0, rgb565(255, 0, 0))
        d.show()
        self.assertEqual(d.spi.writes[:5], [b'\x2a', b'\0\0\x01\x3f',
                         b'\x2b', b'\0\0\0\xef', b'\x2c'])
        payload = b''.join(d.spi.writes[5:])
        self.assertEqual(payload, bytes(d.buffer))
        self.assertEqual(payload[:2], b'\xf8\x00')
        self.assertEqual(d.cs.current, 1)
        d.close()
        self.assertTrue(d.spi.closed)

    def test_all_scenarios_fit_screen(self):
        d = Display()
        ui = Dashboard(d)
        source = DemoSource()
        for i in range(len(SCENARIOS) * 2):
            ui.draw(source.read(), 9999 + i)
        # Extremos del formato soportado para el CO2.
        for co2 in (0, 799, 800, 1199, 1200, 9999):
            data = source.read()
            data['co2'] = co2
            ui.draw(data, 0)

    def test_demo_cycle_and_boundaries(self):
        source = DemoSource()
        first = source.read()
        for _ in range(len(SCENARIOS) - 1):
            source.read()
        self.assertEqual(source.read(), first)
        self.assertTrue(first['demo'])
        for value, expected in [(799, 'BAJO'), (800, 'MEDIO'),
                                 (1199, 'MEDIO'), (1200, 'ALTO')]:
            self.assertEqual(co2_style(value)[0], expected)

    def test_cs_released_on_write_error(self):
        d = Display()
        def fail(data):
            raise OSError('SPI simulado')
        d.spi.write = fail
        with self.assertRaises(OSError):
            d.show()
        self.assertEqual(d.cs.current, 1)


if __name__ == '__main__':
    unittest.main()
