import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'regression_tests'))
import test_firmware
from ili9341 import Display
from ui import Dashboard
from menu import Navigation, ITEMS, menu_rect, MENU_BUTTON, CLOCK_CANCEL
from tft_environment import assess
from tft_layout import LandscapeTouch, portrait_to_landscape

class LandscapeTests(unittest.TestCase):
    def test_environment_boundaries_and_missing(self):
        def state(c=700,t=22,h=40):
            return assess({'co2':c,'temperature':t,'humidity':h})[0]
        self.assertEqual(state(),'happy')
        for c in (1000,1500):self.assertEqual(state(c=c),'neutral')
        self.assertEqual(state(c=1501),'concerned')
        for t in (18,24):self.assertEqual(state(t=t),'happy')
        for t in (17.9,24.1):self.assertEqual(state(t=t),'neutral')
        self.assertEqual(state(h=50),'happy')
        self.assertEqual(state(h=50.1),'neutral')
        self.assertEqual(state(h=60),'concerned')
        for v in (None,float('nan'),float('inf'),-1,'700'):
            self.assertEqual(state(c=v),'unknown')
        self.assertEqual(state(h=101),'unknown')
        self.assertEqual(assess({})[0],'unknown')
        self.assertEqual(assess({'co2':700,'temperature':22,'humidity':40,'pressure':0})[0],'happy')

    def test_render_key_handles_unknown_and_threshold_crossing(self):
        from rendering import render_key
        nav=SimpleNamespace(page='home',touch=None)
        data=dict(co2=700,temperature=23.99,humidity=40,pressure=1013)
        first=render_key(nav,data,1,None,'--:--')
        data['temperature']=24.01
        self.assertNotEqual(first,render_key(nav,data,2,None,'--:--'))
        for key in data:data[key]=None
        render_key(nav,data,3,None,'--:--')

    def test_rotated_existing_calibration_and_boundaries(self):
        touch=SimpleNamespace(matrix=(1,0,0,0,1,0),calibration_state='loaded')
        mapped=LandscapeTouch(touch)
        for p in ((0,0),(239,0),(0,319),(239,319),(120,160)):
            self.assertEqual(mapped.screen_point(p),portrait_to_landscape(p))
        self.assertIsNone(mapped.screen_point((240,10)))
        self.assertIsNone(mapped.screen_point((10,320)))
        self.assertEqual(touch.matrix,(1,0,0,0,1,0))

    def test_real_touch_adapter_navigates_and_calibrates_without_rewriting_saved_matrix(self):
        from touch import Touch, TARGETS, CHECK_TARGET
        from unittest.mock import patch
        import config
        from menu import contains
        with patch('builtins.open',side_effect=OSError):
            touch=Touch(Display())
        touch.matrix=(1,0,0,0,1,0)
        touch.calibration_state='loaded'
        nav=Navigation(touch)
        # Convert horizontal button center to the raw portrait coordinates.
        def raw(r):
            x,y=r[0]+r[2]//2,r[1]+r[3]//2
            return (239-y,x)
        nav.handle(raw(MENU_BUTTON))
        self.assertEqual(nav.page,'menu')
        nav.handle(raw(menu_rect(2)))
        self.assertEqual(nav.page,'calibrate')
        for target in TARGETS:
            nav.handle((target[0]*10+100,target[1]*10+200))
        self.assertIsNotNone(nav.candidate)
        self.assertEqual(nav.page,'calibrate')
        with patch.object(touch,'save',wraps=touch.save) as save, patch('builtins.open',side_effect=OSError):
            nav.handle((CHECK_TARGET[0]*10+100,CHECK_TARGET[1]*10+200))
        self.assertEqual(nav.page,'home')
        self.assertFalse(nav.saved)
        self.assertEqual(touch.calibration_state,'unsaved')
        # New matrix is still portrait; navigating via the adapter works in RAM.
        x,y=raw(MENU_BUTTON)
        nav.handle((x*10+100,y*10+200))
        self.assertEqual(nav.page,'menu')

    def test_preserved_modules_and_configuration(self):
        root=Path(__file__).resolve().parents[1]
        import json,hashlib
        base=json.loads((root/'BASE_SHA256.json').read_text())
        allowed={'ui.py','main.py','firmware_version.py','local_api.py','rendering.py','web_page.py','scd41.py','bme280_float.py','bme280_periodic.py','sensor_source.py'}
        for p in (root/'firmware').glob('*.py'):
            if p.name not in allowed:self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),base[p.name],p.name)
        import config
        self.assertEqual((config.WIDTH,config.HEIGHT,config.MADCTL),(320,240,0x28))
        self.assertEqual(config.SPI_HZ,10000000)

    def test_all_screens_and_states_fit(self):
        ui=Dashboard(Display())
        self.assertEqual((ui.display.width,ui.display.height),(320,240))
        for c,t,h in ((700,22,40),(1200,25,55),(1800,16,65),(None,22,40),(10000,22,40)):
            ui.draw(dict(co2=c,temperature=t,humidity=h,pressure=1013),0,'SIN WIFI')
        link=SimpleNamespace(enabled=False,synced=False)
        for page in ('menu','network','about'):
            ui.draw_menu(page,link,'unsaved',api_state={'state':'ready','url':'http://192.168.100.100:8080'})
        for n in range(3):ui.draw_calibration(n,error=True)
        ui.draw_calibration(3,checking=True)
        ui.draw_settings(2000,'Atlantic/Canary','ERROR: no guardado','unsaved')
        from history import History
        hist=History()
        for i in range(5):hist.add(i,dict(co2=700+i,temperature=22,humidity=40,pressure=1013))
        for metric in range(4):ui.draw_trends(hist,metric)
        from menu import ClockEditor
        clock=SimpleNamespace(snapshot=lambda:{'local':None})
        editor=ClockEditor(clock,'Europe/Madrid')
        editor.ambiguous=True;editor.message='Elegir verano/invierno'
        ui.draw_clock(editor,'Europe/Madrid','unset')

    def test_all_menu_buttons_navigate(self):
        # Test double already supplies horizontal points; real touch mapping tested above.
        class Touch:
            matrix=(1,0,0,0,1,0)
            def screen_point(self,p):return p
        def center(r):return (r[0]+r[2]//2,r[1]+r[3]//2)
        for i,(_,target) in enumerate(ITEMS):
            nav=Navigation(Touch(),clock=SimpleNamespace(snapshot=lambda:{'local':None}))
            nav.handle(center(MENU_BUTTON));self.assertEqual(nav.page,'menu')
            nav.handle(center(menu_rect(i)));self.assertEqual(nav.page,target)
            if target=='clock':
                nav.handle(center(CLOCK_CANCEL));self.assertEqual(nav.page,'menu')


    def test_setup_confirmation_and_updates_fit_existing_geometry(self):
        ui=Dashboard(Display())
        for state in ('checking','available','installing','error','current','trial'):
            ui.draw_updates(state,'v0.10.0','Revisa red, hora y publicacion')
        ui.draw_wifi_confirm()
        ui.draw_wifi_confirm('No se pudo borrar. Reintenta.')
        for state in ('ready','connecting','failed','connected','expired','setup_error'):
            ui.draw_setup({'state':state,'ap_ssid':'AURA-ABCDEF','ip':'192.168.100.100','error':None},'ABC234','ABCD2345')
