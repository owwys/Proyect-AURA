import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import test_firmware
import config
from ili9341 import Display
from touch import Touch, affine, TARGETS
from menu import Navigation
from settings import Settings
from demo import DemoSource
from ui import Dashboard

class V07Tests(unittest.TestCase):
    def setUp(self):
        for name, value in (('UPDATE_MS', 2000), ('TIMEZONE', 'Europe/Madrid')):
            p = patch.object(config, name, value)
            p.start()
            self.addCleanup(p.stop)

    def test_static_menu_does_not_redraw_for_new_samples_or_clock(self):
        from rendering import render_key, FrameGate
        nav = Navigation(None)
        nav.page = 'menu'
        gate = FrameGate()
        data = DemoSource().read()
        key = render_key(nav, data, 1, None, '12:00')
        self.assertTrue(gate.ready(key, False))
        gate.commit(key)
        for revision in range(2, 102):
            key = render_key(nav, DemoSource().read(), revision, None, '12:01')
            self.assertFalse(gate.ready(key, False))

    def test_home_updates_only_visible_changes_and_defers_during_touch(self):
        from rendering import render_key, FrameGate
        from types import SimpleNamespace
        nav = Navigation(None)
        data = DemoSource().read()
        link = SimpleNamespace(caption=lambda:'WIFI OK / NTP OK', synced=True)
        gate = FrameGate()
        key = render_key(nav, data, 1, link, '12:00')
        self.assertTrue(gate.ready(key, True))  # Paint initial screen even if held.
        gate.commit(key)
        self.assertFalse(gate.ready(render_key(nav, data, 2, link, '12:00'), False))
        link.caption = lambda:'WIFI OK / RTC OK'
        self.assertFalse(gate.ready(render_key(nav, data, 3, link, '12:00'), False))
        new_key = render_key(nav, data, 3, link, '12:01')
        self.assertFalse(gate.ready(new_key, True))
        self.assertTrue(gate.ready(new_key, False))
        gate.commit(new_key)
        data['co2'] = 950
        self.assertTrue(gate.ready(render_key(nav, data, 4, link, '12:01'), False))

    def test_trends_update_when_history_changes(self):
        from rendering import render_key
        nav = Navigation(None)
        nav.page = 'trends'
        key = render_key(nav, {}, 120, None, '--:--')
        self.assertNotEqual(key, render_key(nav, {}, 121, None, '--:--'))
        nav.metric = 1
        self.assertNotEqual(key, render_key(nav, {}, 120, None, '--:--'))

    def test_calibration_status_load_save_and_failed_write(self):
        from rendering import calibration_status
        with tempfile.TemporaryDirectory() as d, patch.object(config,'TOUCH_CALIBRATION_FILE',str(Path(d)/'cal.json')):
            touch = Touch(Display())
            self.assertEqual(calibration_status(touch), 'pending')
            matrix = affine([(x*10+100,y*10+200) for x,y in TARGETS])
            with patch('touch.open', side_effect=OSError):
                self.assertFalse(touch.save(matrix))
            self.assertEqual(calibration_status(touch), 'unsaved')
            self.assertIsNotNone(touch.screen_point((1300,1800)))
            self.assertTrue(touch.save(matrix))
            self.assertEqual(calibration_status(touch), 'saved')
            self.assertEqual(calibration_status(Touch(Display())), 'loaded')
            self.assertEqual(calibration_status(None), 'disabled')

    def test_touch_busy_includes_release_debounce(self):
        from rendering import touch_busy
        from types import SimpleNamespace
        irq = test_firmware.Pin(7, value=1)
        t = SimpleNamespace(irq=irq, tracker=SimpleNamespace(started=None))
        self.assertFalse(touch_busy(t))
        irq.value(0)
        self.assertTrue(touch_busy(t))
        irq.value(1)
        t.tracker.started = 0
        self.assertTrue(touch_busy(t))
        t.tracker.started = None
        self.assertFalse(touch_busy(t))

    def test_settings_no_change_and_failed_save_visible(self):
        class FakeTouch:
            matrix = (1,0,0,0,1,0)
            def screen_point(self, p): return p
        with tempfile.TemporaryDirectory() as d:
            settings = Settings(str(Path(d)/'s.json'))
            nav = Navigation(FakeTouch(),settings)
            nav.page = 'settings'
            for _ in range(3): nav.handle((80,80))
            self.assertEqual(nav.message, 'Sin cambios')
            nav.handle((80,80))
            self.assertEqual(nav.message, 'Pendiente de guardar')
            with patch('settings.os.rename', side_effect=OSError): nav.handle((80,128))
            self.assertEqual(nav.message,'ERROR: no guardado')
            self.assertEqual(settings.interval,2000)
            nav.handle((80,128))
            self.assertEqual(settings.interval,5000)
            self.assertEqual(nav.message,'Guardado')

    def test_status_labels_fit_and_unsaved_warning_drawn_on_home(self):
        from rendering import CALIBRATION_LABELS
        ui = Dashboard(Display())
        for state in CALIBRATION_LABELS:
            ui.draw_settings(2000,'Europe/Madrid','Pendiente de guardar',state)
            from types import SimpleNamespace
            ui.draw_menu('menu',SimpleNamespace(enabled=False,synced=False),state)
        with patch.object(ui.g, 'text', wraps=ui.g.text) as text:
            ui.draw(DemoSource().read(),0,'SIN WIFI',False,'unsaved')
            self.assertTrue(any('SIN GUARDAR' in c.args[0] for c in text.call_args_list))

    def test_diagnostics_measure_elapsed_event_to_frame_and_wrap(self):
        from diagnostics import Diagnostics
        stats = Diagnostics()
        with patch('diagnostics.time.ticks_diff',side_effect=lambda a,b:((a-b+512)%1024)-512,create=True):
            stats.poll(1000)
            stats.poll(10)
            stats.event(1000)
            stats.frame(12, 130000)
        self.assertEqual(stats.max_poll_ms,34)
        self.assertEqual(stats.max_response_ms,36)
        self.assertEqual(stats.frames,1)
        self.assertEqual(stats.frame_us,130000)

    def test_main_keeps_static_menu_one_frame_while_history_grows(self):
        import test_connectivity
        import main
        from types import SimpleNamespace
        from history import History
        class RecordingDisplay(Display):
            def __init__(self):
                self.transfers = 0
                super().__init__()
            def show(self):
                self.transfers += 1
                super().show()
        class FakeTouch:
            matrix = (1,0,0,0,1,0)
            irq = test_firmware.Pin(7, value=1)
            def __init__(self, display): self.first = True
            def poll(self):
                if self.first:
                    self.first = False
                    return (290,20)
            def screen_point(self, p): return p
        tick = [0]
        def clock(): return tick[0]
        def pause(ms):
            tick[0] += ms
            if tick[0] >= 12000: raise KeyboardInterrupt
        display = RecordingDisplay()
        history = History()
        link = SimpleNamespace(enabled=False, synced=False, caption=lambda:'SIN WIFI', poll=lambda:None)
        with tempfile.TemporaryDirectory() as d:
            settings = Settings(str(Path(d)/'s.json'))
            with patch('main.Settings',return_value=settings), patch('main.History',return_value=history), \
                 patch('main.Display',return_value=display), patch('main.Touch',FakeTouch), \
                 patch('main.Connectivity',return_value=link), \
                 patch('main.time.ticks_ms',side_effect=clock,create=True), \
                 patch('main.time.ticks_diff',side_effect=lambda a,b:a-b,create=True), \
                 patch('main.time.sleep_ms',side_effect=pause):
                main.run()
        self.assertEqual(display.transfers,2)  # One init clear, one menu image.
        self.assertEqual(len(history.series('co2')),6)
        self.assertTrue(display.spi.closed)

    def test_main_defers_network_during_release_debounce(self):
        import test_connectivity
        import main
        from types import SimpleNamespace
        polls = []
        tick = [0]
        class FakeTouch:
            matrix = (1,0,0,0,1,0)
            irq = test_firmware.Pin(7,value=1)
            tracker = SimpleNamespace(started=0)
            def __init__(self, display): pass
            def poll(self):
                self.tracker.started = 0 if tick[0] < 40 else None
            def screen_point(self, p): return p
        def pause(ms):
            tick[0] += ms
            if tick[0] >= 80: raise KeyboardInterrupt
        display = Display()
        link = SimpleNamespace(enabled=False,synced=False,caption=lambda:'SIN WIFI',
                               poll=lambda:polls.append(tick[0]))
        with tempfile.TemporaryDirectory() as d:
            settings = Settings(str(Path(d)/'s.json'))
            with patch('main.Settings',return_value=settings), patch('main.Touch',FakeTouch), patch('main.Display',return_value=display), \
                 patch('main.Connectivity',return_value=link), \
                 patch('main.time.ticks_ms',side_effect=lambda:tick[0],create=True), \
                 patch('main.time.ticks_diff',side_effect=lambda a,b:a-b,create=True), \
                 patch('main.time.sleep_ms',side_effect=pause): main.run()
        self.assertEqual(polls,[40,60])

    def test_diagnostics_counts_only_events_that_change_image(self):
        import test_connectivity
        import main
        import diagnostics
        from types import SimpleNamespace
        stats = diagnostics.Diagnostics()
        tick = [0]
        class FakeTouch:
            matrix = (1,0,0,0,1,0)
            irq = test_firmware.Pin(7,value=1)
            def __init__(self, display):
                self.events = iter(((290,20),(230,130),(80,80),(80,128),(80,128)))
            def poll(self): return next(self.events)
            def screen_point(self,p): return p
        def pause(ms):
            tick[0] += ms
            if tick[0] >= 100: raise KeyboardInterrupt
        display = Display()
        link = SimpleNamespace(enabled=False,synced=False,caption=lambda:'SIN WIFI',poll=lambda:None)
        with tempfile.TemporaryDirectory() as d:
            settings = Settings(str(Path(d)/'s.json'))
            with patch('main.Settings',return_value=settings), patch('main.Display',return_value=display), \
                 patch('main.Touch',FakeTouch), patch('main.Connectivity',return_value=link), \
                 patch('diagnostics.Diagnostics',return_value=stats), \
                 patch('diagnostics.gc.mem_free',return_value=8000000,create=True), \
                 patch('main.time.ticks_ms',side_effect=lambda:tick[0],create=True), \
                 patch('main.time.ticks_us',side_effect=lambda:tick[0]*1000,create=True), \
                 patch('main.time.ticks_diff',side_effect=lambda a,b:a-b,create=True), \
                 patch('main.time.sleep_ms',side_effect=pause): main.run(diagnostics=True)
        self.assertEqual(stats.frames,4)
        self.assertEqual(stats.events,4)
        self.assertEqual(stats.response_events,4)
        self.assertIsNone(stats.pending_event)

    def test_disabled_touch_is_visible_on_home_without_menu_access(self):
        from rendering import calibration_status
        nav = Navigation(None)
        self.assertEqual(nav.page,'home')
        ui = Dashboard(Display())
        with patch.object(ui.g,'text',wraps=ui.g.text) as text:
            ui.draw(DemoSource().read(),0,'SIN WIFI',False,calibration_status(nav.touch))
        self.assertTrue(any('TACTIL DESACTIVADO' in c.args[0] for c in text.call_args_list))
