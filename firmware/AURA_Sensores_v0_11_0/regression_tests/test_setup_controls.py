import unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
import test_firmware,test_connectivity
from wifi_store import WiFiStore

class SetupControlTests(unittest.TestCase):
    def test_skip_closes_without_writing_storage(self):
        from setup_mode import SetupMode
        from unittest.mock import Mock
        mode=SetupMode.__new__(SetupMode);mode.close=Mock()
        with patch('builtins.open',side_effect=AssertionError('No escribir al omitir')):
            self.assertTrue(mode.skip())
        mode.close.assert_called_once()

    def test_reset_discards_runtime_skip(self):
        import connectivity
        with patch('time.ticks_ms',return_value=0,create=True),patch.object(WiFiStore,'load',return_value=None), \
             patch.object(test_connectivity.wifi_config,'SSID',''):
            link=connectivity.Connectivity();self.assertTrue(link.setup_needed)
            link.offline();self.assertFalse(link.setup_needed)
            rebooted=connectivity.Connectivity();self.assertTrue(rebooted.setup_needed)

    def test_confirmed_clear_removes_json_and_legacy_secrets(self):
        with tempfile.TemporaryDirectory() as d:
            store=WiFiStore(str(Path(d)/'wifi.json'));legacy=Path(d)/'wifi_config.py'
            legacy.write_text("SSID='Antigua'\nPASSWORD='secreto123'\n")
            store.save('Casa','12345678',False)
            store.clear(str(legacy))
            self.assertIsNone(store.load())
            self.assertNotIn('secreto123',legacy.read_text())
            self.assertNotIn('12345678',Path(store.path).read_text())

    def test_cannot_erase_existing_json_if_legacy_write_fails(self):
        with tempfile.TemporaryDirectory() as d:
            store=WiFiStore(str(Path(d)/'wifi.json'));store.save('Casa','12345678',False)
            with self.assertRaises(OSError):store.clear(str(Path(d)/'missing'/'wifi_config.py'))
            self.assertEqual(store.load(),('Casa','12345678'))

    def test_navigation_asks_before_reset_and_cancel_is_inert(self):
        from menu import Navigation,ITEMS,menu_rect
        from tft_layout import WIFI_CANCEL,WIFI_CONFIRM
        touch=SimpleNamespace(matrix=(1,0,0,0,1,0),screen_point=lambda p:p)
        nav=Navigation(touch);nav.page='menu'
        index=[target for _,target in ITEMS].index('wifi_confirm')
        def center(r):return r[0]+r[2]//2,r[1]+r[3]//2
        nav.handle(center(menu_rect(index)))
        self.assertEqual(nav.page,'wifi_confirm');self.assertIsNone(nav.wifi_action)
        nav.handle(center(WIFI_CANCEL));self.assertEqual(nav.page,'menu');self.assertIsNone(nav.wifi_action)
        nav.handle(center(menu_rect(index)));nav.handle(center(WIFI_CONFIRM))
        self.assertEqual(nav.wifi_action,'reset')

    def test_credentials_bypass_setup_even_when_old_debug_flag_true(self):
        import connectivity,config
        from wifi_store import WiFiStore
        with patch('time.ticks_ms',return_value=0,create=True),patch.object(config,'SETUP_ON_BOOT',True,create=True),patch.object(WiFiStore,'load',return_value=('Casa','12345678')):
            link=connectivity.Connectivity()
        self.assertTrue(link.enabled);self.assertFalse(link.setup_needed)

class MainSetupControlTests(unittest.TestCase):
    def test_saved_network_ignores_legacy_force_flag(self):
        self.run_main_controls(events=[None,None],has_wifi=True,expect_setup=False)

    def test_cancel_then_confirm_and_skip(self):
        from tft_layout import WIFI_CANCEL,WIFI_CONFIRM,SETUP_SKIP,menu_rect
        def center(r):return r[0]+r[2]//2,r[1]+r[3]//2
        events=[(290,20),center(menu_rect(7)),center(WIFI_CANCEL),center(menu_rect(7)),center(WIFI_CONFIRM),center(SETUP_SKIP)]
        self.run_main_controls(events=events,has_wifi=True,expect_setup=True)

    def run_main_controls(self,events,has_wifi,expect_setup):
        from unittest.mock import Mock
        from clock_service import ClockService
        from test_clock_service import FakeRTC
        from ili9341 import Display
        from settings import Settings
        from local_api import LocalAPI
        import main,config
        tick=[0];remaining=iter(events)
        class Touch:
            matrix=(1,0,0,0,1,0)
            irq=test_firmware.Pin(7,value=1)
            def __init__(self,display):pass
            def screen_point(self,p):return p
            def poll(self):return next(remaining)
        wlan=SimpleNamespace(isconnected=lambda:False,ifconfig=lambda:('0.0.0.0','','',''))
        link=SimpleNamespace(enabled=has_wifi,setup_needed=not has_wifi,synced=False,wlan=wlan,
            caption=lambda:'SIN WIFI',poll=Mock(),offline=Mock(),forget=Mock())
        mode=SimpleNamespace(session=SimpleNamespace(state='ready',active=True),wifi_key='ABCD2345',key='ABCD2345',
            snapshot=lambda:{'state':'ready','ap_ssid':'AURA-ABCDEF','ip':None},poll=Mock(),skip=Mock(return_value=True),close=Mock())
        def pause(ms):
            tick[0]+=ms
            if expect_setup and tick[0]<=80:link.forget.assert_not_called()
            if tick[0]>=len(events)*config.TOUCH_POLL_MS:raise KeyboardInterrupt
        with tempfile.TemporaryDirectory() as d,patch.object(config,'SETUP_ON_BOOT',True,create=True):
            with patch('main.ClockService',return_value=ClockService(FakeRTC())),patch('main.Settings',return_value=Settings(str(Path(d)/'settings.json'))), \
                 patch('main.Display',return_value=Display()),patch('main.Touch',Touch),patch('main.Connectivity',return_value=link), \
                 patch('main.LocalAPI',return_value=LocalAPI(lambda:{},enabled=False)),patch('setup_mode.SetupMode',return_value=mode) as create, \
                 patch('main.time.ticks_ms',side_effect=lambda:tick[0],create=True),patch('main.time.ticks_diff',side_effect=lambda a,b:a-b,create=True), \
                 patch('main.time.sleep_ms',side_effect=pause):main.run()
        if expect_setup:
            create.assert_called_once();link.forget.assert_called_once();mode.skip.assert_called_once();link.offline.assert_called_once()
        else:create.assert_not_called();link.forget.assert_not_called()
