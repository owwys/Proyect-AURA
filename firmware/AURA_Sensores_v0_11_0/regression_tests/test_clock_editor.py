import unittest
from unittest.mock import patch
import test_firmware
import config
from test_clock_service import FakeRTC
from clock_service import ClockService
from ui import Dashboard
from ili9341 import Display
from menu import Navigation

class IdentityTouch:
    matrix=(1,0,0,0,1,0)
    def screen_point(self,p):return p

class EditorTests(unittest.TestCase):
    def setUp(self):
        self.rtc=FakeRTC();self.clock=ClockService(self.rtc)
        p=patch.object(config,'TIMEZONE','Europe/Madrid');p.start();self.addCleanup(p.stop)

    def test_draft_clamp_and_cancel(self):
        from menu import ClockEditor
        editor=ClockEditor(self.clock,'Europe/Madrid')
        editor.parts=[2028,2,29,12,0];editor.select(0);editor.step(1)
        self.assertEqual(editor.parts[:3],[2029,2,28])
        editor.parts=[2026,3,31,12,0];editor.select(1);editor.step(1)
        self.assertEqual(editor.parts[:3],[2026,4,30])
        self.assertFalse(self.clock.ready)
        with self.assertRaises(ValueError):editor.select(5)
        nav=Navigation(IdentityTouch(),clock=self.clock)
        nav.handle((290,20));nav.handle((80,168))
        self.assertEqual(nav.page,'clock')
        nav.handle((230,210))
        self.assertEqual(nav.page,'menu');self.assertFalse(self.clock.ready)

    def test_edit_draft_survives_ntp_and_rtc_failure(self):
        from menu import ClockEditor
        editor=ClockEditor(self.clock,'Europe/Madrid')
        editor.parts=[2026,10,16,15,25]
        self.rtc.stamp=(2026,10,16,4,11,0,0,0);self.clock.mark_ntp(1792148400)
        self.assertEqual(editor.parts,[2026,10,16,15,25])
        self.rtc.fail=True
        self.assertFalse(editor.apply('Europe/Madrid'));self.assertFalse(editor.applied)
        self.rtc.fail=False
        self.assertTrue(editor.apply('Europe/Madrid'))
        self.assertEqual(self.clock.source,'manual')

    def test_gap_and_fold_choice(self):
        from menu import ClockEditor
        editor=ClockEditor(self.clock,'Europe/Madrid')
        editor.parts=[2026,3,29,2,30]
        self.assertFalse(editor.apply('Europe/Madrid'))
        editor.parts=[2026,10,25,2,30]
        self.assertFalse(editor.apply('Europe/Madrid'));self.assertTrue(editor.ambiguous)
        editor.fold='winter'
        self.assertTrue(editor.apply('Europe/Madrid'))
        self.assertEqual(self.rtc.stamp[4],1)
        editor.step(1);self.assertIsNone(editor.fold)

    def test_editor_and_menu_fit_and_manual_home_visible(self):
        from menu import ClockEditor
        editor=ClockEditor(self.clock,'Europe/Madrid')
        ui=Dashboard(Display())
        for message in ('','ERROR: no aplicada','Hora local inexistente','Elegir verano/invierno'):
            editor.message=message
            ui.draw_clock(editor,'Europe/Madrid','unset')
        editor.ambiguous=True
        ui.draw_clock(editor,'Europe/Madrid','unset')
        self.clock.set_local((2026,10,16,15,25),'Europe/Madrid')
        with patch.object(ui.g,'text',wraps=ui.g.text) as text:
            from demo import DemoSource
            ui.draw(DemoSource().read(),0,'SIN WIFI',self.clock.ready,'loaded',self.clock)
        self.assertTrue(any(c.args[0]=='15:25' for c in text.call_args_list))
        from types import SimpleNamespace
        ui.draw_menu('menu',SimpleNamespace(enabled=False,synced=False))
