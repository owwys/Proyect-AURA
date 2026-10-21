import os
import tempfile
import types
import unittest
from unittest.mock import patch
import test_firmware
import config
from touch import Touch, TapTracker, affine, apply, TARGETS, CHECK_TARGET
from menu import Navigation, contains
from ili9341 import Display
from ui import Dashboard


def ticks_diff(a, b):
    return ((a-b+(1 << 29)) % (1 << 30))-(1 << 29)


class TouchTests(unittest.TestCase):
    def test_affine_swapped_and_inverted_axes(self):
        raw = [(4095-y*10, 300+x*12) for x, y in TARGETS]
        matrix = affine(raw)
        for point in TARGETS + (CHECK_TARGET, (0, 0), (239, 319)):
            self.assertEqual(apply(matrix, (4095-point[1]*10, 300+point[0]*12)), point)
        with self.assertRaises(ValueError):
            affine([(100, 100)]*3)

    def test_touch_bus_and_cs_restored_after_error(self):
        display = Display()
        with patch('touch.open', side_effect=OSError):
            touch = Touch(display)
        self.assertEqual(touch.read_raw(), (1000, 2000))
        self.assertEqual(touch.cs.value(), 1)
        self.assertEqual(display.cs.value(), 1)
        self.assertEqual(display.spi.last_init['baudrate'], config.SPI_HZ)
        with patch.object(display.spi, 'write_readinto', side_effect=OSError):
            with self.assertRaises(OSError):
                touch.read_raw()
        self.assertEqual(touch.cs.value(), 1)
        self.assertEqual(display.spi.last_init['baudrate'], config.SPI_HZ)

    def test_tap_once_on_release_not_hold_and_bounce(self):
        with patch('touch.time.ticks_diff', side_effect=ticks_diff, create=True):
            tracker = TapTracker()
            self.assertIsNone(tracker.update((500, 600), True, 0))
            self.assertIsNone(tracker.update((501, 600), True, 80))
            self.assertIsNone(tracker.update(None, False, 100))
            self.assertEqual(tracker.update(None, False, 140), (501, 600))
            self.assertIsNone(tracker.update(None, False, 180))
            tracker.update((1, 2), True, 200)
            tracker.update(None, False, 210)
            self.assertIsNone(tracker.update(None, False, 250))

    def test_calibration_save_load_and_invalid_file(self):
        display = Display()
        with tempfile.TemporaryDirectory() as folder:
            filename = os.path.join(folder, 'cal.json')
            with patch.object(config, 'TOUCH_CALIBRATION_FILE', filename):
                touch = Touch(display)
                self.assertIsNone(touch.matrix)
                matrix = affine([(x*10+100, y*10+200) for x, y in TARGETS])
                self.assertTrue(touch.save(matrix))
                again = Touch(display)
                self.assertEqual(again.screen_point((1300, 1800)), (120, 160))
                with open(filename, 'w') as f:
                    f.write('corrupto')
                self.assertIsNone(Touch(display).matrix)

    def test_calibration_requires_fourth_check_then_menu_navigation(self):
        class FakeTouch:
            matrix = None
            def save(self, matrix):
                self.matrix = matrix
                return True
            def screen_point(self, raw):
                return apply(self.matrix, raw)
        touch = FakeTouch()
        nav = Navigation(touch)
        raw = lambda p: (100+p[0]*10, 200+p[1]*10)
        for target in TARGETS:
            nav.handle(raw(target))
        self.assertEqual(nav.page, 'calibrate')
        nav.handle(raw(CHECK_TARGET))
        self.assertEqual(nav.page, 'home')
        nav.handle(raw((290, 20)))
        self.assertEqual(nav.page, 'menu')
        nav.handle(raw((230, 55)))
        self.assertEqual(nav.page, 'network')
        nav.handle(raw((260, 210)))
        self.assertEqual(nav.page, 'menu')
        nav.handle(raw((80, 90)))
        self.assertEqual(nav.page, 'calibrate')
        for target in TARGETS:
            nav.handle(raw(target))
        nav.handle(raw((20, 100)))
        self.assertEqual(nav.page, 'calibrate')
        self.assertTrue(nav.error)
        self.assertIsNone(nav.candidate)

    def test_all_menu_and_calibration_screens_fit(self):
        ui = Dashboard(Display())
        link = types.SimpleNamespace(enabled=False, synced=False)
        for page in ('menu', 'network', 'about'):
            ui.draw_menu(page, link)
        for index in range(3):
            ui.draw_calibration(index)
        ui.draw_calibration(3, True, True)
        self.assertTrue(contains((10, 10, 20, 20), (10, 10)))
        self.assertFalse(contains((10, 10, 20, 20), (30, 30)))
