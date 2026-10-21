import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import test_firmware
from ili9341 import Display
from ui import Dashboard
from menu import Navigation
from demo import DemoSource

class V06Tests(unittest.TestCase):
    def setUp(self):
        import config
        for name, value in (('UPDATE_MS', 2000), ('TIMEZONE', 'Europe/Madrid')):
            p = patch.object(config, name, value)
            p.start()
            self.addCleanup(p.stop)

    def test_history_bounded_chronological_and_real_time(self):
        from history import History
        h = History(3)
        for t, v in ((0, 650), (2, 780), (7, 950), (17, 1250)):
            h.add(t, dict(co2=v, temperature=22.5, humidity=48, pressure=1013))
        self.assertEqual(h.series('co2'), [(2,780), (7,950), (17,1250)])
        self.assertEqual(History(3).series('co2'), [])

    def test_settings_reload_corruption_and_failed_save(self):
        from settings import Settings
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d)/'settings.json')
            s = Settings(path)
            self.assertEqual(s.interval, 2000)
            self.assertTrue(s.save(5000, 'UTC'))
            loaded = Settings(path)
            self.assertEqual((loaded.interval, loaded.zone), (5000, 'UTC'))
            self.assertFalse(s.save(0, 'UTC'))
            self.assertFalse(s.save(2000, 'unknown'))
            with patch('settings.open', side_effect=OSError):
                self.assertFalse(s.save(10000, 'Europe/Madrid'))
            self.assertEqual((s.interval, s.zone), (5000, 'UTC'))
            Path(path).write_text('{"interval": true, "zone": []}')
            self.assertEqual(Settings(path).interval, 2000)

    def test_navigation_settings_save_and_trends(self):
        from settings import Settings
        class Touch:
            matrix = (1,0,0,0,1,0)
            def screen_point(self, p): return p
        with tempfile.TemporaryDirectory() as d:
            s = Settings(str(Path(d)/'s.json'))
            nav = Navigation(Touch(), s)
            nav.handle((290,20))
            nav.handle((80,130))
            self.assertEqual(nav.page, 'trends')
            nav.handle((230,174))
            self.assertEqual(nav.metric, 1)
            nav.handle((260,210))
            nav.handle((230,130))
            self.assertEqual(nav.page, 'settings')
            nav.handle((80,80))
            nav.handle((230,80))
            nav.handle((80,128))
            self.assertTrue(nav.saved)
            self.assertEqual(Settings(s.path).interval, 5000)
            self.assertEqual(Settings(s.path).zone, 'Atlantic/Canary')

    def test_trend_empty_single_flat_and_variable_fit(self):
        from history import History
        ui = Dashboard(Display())
        h = History(120)
        ui.draw_trends(h, 0)
        h.add(0, DemoSource().read())
        for metric in range(4): ui.draw_trends(h, metric)
        for i in range(1,125): h.add(i*2, DemoSource().read())
        for metric in range(4): ui.draw_trends(h, metric)

    def test_settings_screen_and_runtime_timezone(self):
        from settings import Settings
        import config
        with tempfile.TemporaryDirectory() as d:
            s = Settings(str(Path(d)/'s.json'))
            with patch.object(config, 'TIMEZONE', config.TIMEZONE), patch.object(config, 'UPDATE_MS', config.UPDATE_MS):
                s.save(10000, 'UTC')
                s.apply()
                self.assertEqual(config.TIMEZONE, 'UTC')
                self.assertEqual(config.UPDATE_MS, 10000)
                ui = Dashboard(Display())
                ui.draw_settings(s.interval, s.zone, 'Guardado')

    def test_settings_replace_existing_file_and_rename_failure(self):
        from settings import Settings
        with tempfile.TemporaryDirectory() as d:
            s = Settings(str(Path(d)/'s.json'))
            self.assertTrue(s.save(5000, 'UTC'))
            self.assertTrue(s.save(10000, 'Europe/Madrid'))
            with patch('settings.os.rename', side_effect=OSError):
                self.assertFalse(s.save(2000, 'UTC'))
            loaded = Settings(s.path)
            self.assertEqual((loaded.interval, loaded.zone), (10000, 'Europe/Madrid'))

    def test_main_loop_offline_collects_and_draws_all_new_pages(self):
        import test_connectivity
        import main
        import config
        from history import History
        from settings import Settings
        class FakeTouch:
            matrix = (1,0,0,0,1,0)
            irq = test_firmware.Pin(7, pull=test_firmware.Pin.PULL_UP)
            def __init__(self, display):
                self.events = iter(((290,20),(80,130),(230,174),(260,210),
                                    (230,130),(80,80),(230,80),(80,128),None))
            def poll(self): return next(self.events)
            def screen_point(self, p): return p
        tick = [0]
        def clock():
            tick[0] += 1000
            return tick[0]
        pauses = [0]
        def pause(ms):
            pauses[0] += 1
            if pauses[0] == 9: raise KeyboardInterrupt
        with tempfile.TemporaryDirectory() as d:
            settings = Settings(str(Path(d)/'s.json'))
            history = History()
            display = Display()
            with patch('main.Settings', return_value=settings), patch('main.History', return_value=history),                  patch('main.Display', return_value=display), patch('main.Touch', FakeTouch),                  patch('main.time.ticks_ms', side_effect=clock, create=True),                  patch('main.time.ticks_diff', side_effect=lambda a,b:a-b, create=True), patch('main.time.ticks_add', side_effect=lambda a,b:a+b, create=True),                  patch('main.time.sleep_ms', side_effect=pause),                  patch.object(test_connectivity.wifi_config, 'SSID', 'Configured-but-offline'):
                main.run()
            self.assertTrue(display.spi.closed)
            self.assertGreater(len(history.series('co2')), 1)
            loaded = Settings(settings.path)
            self.assertEqual((loaded.interval, loaded.zone), (5000, 'Atlantic/Canary'))
