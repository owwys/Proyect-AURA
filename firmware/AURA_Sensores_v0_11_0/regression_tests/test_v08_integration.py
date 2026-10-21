import unittest
from unittest.mock import patch
import tempfile
from pathlib import Path
from types import SimpleNamespace
import test_firmware
import test_connectivity
import config
from test_clock_service import FakeRTC
from test_local_api import Listener,Client
from clock_service import ClockService
from local_api import LocalAPI
from settings import Settings
from ili9341 import Display
from demo import DemoSource

class IntegrationTests(unittest.TestCase):
    def setUp(self):
        for key,value in (('UPDATE_MS',2000),('TIMEZONE','Europe/Madrid'),('TOUCH_ENABLED',True)):
            p=patch.object(config,key,value);p.start();self.addCleanup(p.stop)

    def test_api_routes_use_last_sample_and_manual_clock_before_next_sample(self):
        import main
        rtc=FakeRTC();clock=ClockService(rtc)
        listener=Listener();client=Client([b'GET /api/status HTTP/1.0\r\n\r\n'])
        api=LocalAPI(lambda:None,socket_factory=lambda:listener)
        tick=[0];snapshots=[]
        class Touch:
            matrix=(1,0,0,0,1,0)
            irq=test_firmware.Pin(7,value=1)
            def __init__(self,display):
                self.events=iter((None,(290,20),(80,168),(80,210),(230,210),(230,55),None,None,None,None))
            def screen_point(self,p):return p
            def poll(self):return next(self.events)
        display=Display()
        link=SimpleNamespace(enabled=True,synced=False,caption=lambda:'WIFI OK / SIN HORA',poll=lambda:None,
                             wlan=SimpleNamespace(isconnected=lambda:True,ifconfig=lambda:('192.0.2.10','','','')))
        from sensor_source import SensorSource
        source=SensorSource(bus_factory=lambda: (_ for _ in ()).throw(OSError(19)))
        def factory(snapshot_fn,**kwargs):
            def snap():
                result=snapshot_fn();snapshots.append(result);return result
            api.snapshot_fn=snap;return api
        def pause(ms):
            tick[0]+=ms
            if tick[0]==100:listener.pending.append(client)
            if tick[0]>=200:raise KeyboardInterrupt
        with tempfile.TemporaryDirectory() as d:
            settings=Settings(str(Path(d)/'s.json'))
            with patch('main.ClockService',return_value=clock),patch('main.Display',return_value=display), \
                 patch('main.Settings',return_value=settings),patch('main.Touch',Touch), \
                 patch('main.Connectivity',return_value=link),patch('main.SensorSource',return_value=source), \
                 patch('main.LocalAPI',side_effect=factory), \
                 patch('main.time.ticks_ms',side_effect=lambda:tick[0],create=True), \
                 patch('main.time.ticks_diff',side_effect=lambda a,b:a-b,create=True), \
                 patch('main.time.sleep_ms',side_effect=pause):main.run()
        self.assertFalse(snapshots[-1]['measurements']['demo'])
        self.assertIsNone(snapshots[-1]['measurements']['co2_ppm'])
        self.assertEqual(clock.source,'manual')
        self.assertTrue(client.closed);self.assertTrue(listener.closed);self.assertTrue(display.spi.closed)
        self.assertIn(b'200 OK',client.output)
        self.assertTrue(snapshots[-1]['status']['clock']['ready'])
        self.assertIsNone(snapshots[-1]['measurements']['sample_utc'])

    def test_render_error_closes_api_and_display(self):
        import main
        from ui import Dashboard
        display=Display();api=LocalAPI(lambda:{},enabled=False)
        link=SimpleNamespace(enabled=False,synced=False,caption=lambda:'SIN WIFI',poll=lambda:None)
        with tempfile.TemporaryDirectory() as d,patch.object(config,'TOUCH_ENABLED',False):
            with patch('main.ClockService',return_value=ClockService(FakeRTC())), \
                 patch('main.Settings',return_value=Settings(str(Path(d)/'s.json'))), \
                 patch('main.Display',return_value=display),patch('main.LocalAPI',return_value=api), \
                 patch('main.Connectivity',return_value=link), \
                 patch('main.time.ticks_ms',return_value=0,create=True), \
                 patch('main.time.ticks_diff',side_effect=lambda a,b:a-b,create=True), \
                 patch.object(Dashboard,'draw',side_effect=ValueError('dibujo')):
                with self.assertRaises(ValueError):main.run()
        self.assertTrue(display.spi.closed);self.assertEqual(api.client_count,0)

    def test_first_boot_api_available_while_setup_ap_still_active(self):
        import main
        tick=[0]; ips=[]
        session=SimpleNamespace(state='connected',active=True)
        setup=SimpleNamespace(session=session,key='ABC234',wifi_key='ABCD2345',poll=lambda now:None,
            snapshot=lambda:{'state':'connected','ip':'192.0.2.10'},close=lambda:None)
        link=SimpleNamespace(enabled=False,setup_needed=True,synced=False,
            caption=lambda:'SIN WIFI',poll=lambda:None,
            wlan=SimpleNamespace(isconnected=lambda:True,ifconfig=lambda:('192.0.2.10','','','')))
        api=SimpleNamespace(poll=lambda now,ip,**kw:ips.append(ip),status=lambda:{},close=lambda:None)
        def pause(ms):raise KeyboardInterrupt
        with tempfile.TemporaryDirectory() as d,patch.object(config,'TOUCH_ENABLED',False):
            with patch('main.ClockService',return_value=ClockService(FakeRTC())), \
                 patch('main.Settings',return_value=Settings(str(Path(d)/'s.json'))), \
                 patch('main.Display',return_value=Display()),patch('main.LocalAPI',return_value=api), \
                 patch('main.Connectivity',return_value=link),patch('setup_mode.SetupMode',return_value=setup), \
                 patch('main.time.ticks_ms',return_value=0,create=True), \
                 patch('main.time.ticks_diff',side_effect=lambda a,b:a-b,create=True), \
                 patch('main.time.sleep_ms',side_effect=pause):main.run()
        self.assertEqual(ips,['192.0.2.10'])
        self.assertTrue(session.active)
