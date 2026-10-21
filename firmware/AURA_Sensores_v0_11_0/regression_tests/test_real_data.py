import unittest
from unittest.mock import patch
import test_firmware
from ili9341 import Display
from ui import Dashboard
from history import History
from local_api import make_snapshot
from web_page import render

class RealDataTests(unittest.TestCase):
    def data(self):
        return dict(co2=None,temperature=22.6,humidity=44,pressure=941.4,demo=False,
                    sources={'co2':None,'temperature':'bme280','humidity':'bme280','pressure':'bme280'},
                    field_age_ms={'co2':None,'temperature':200,'humidity':200,'pressure':200},
                    sensors={'scd41':{'state':'error','age_ms':None,'error':'CRC'}},
                    sensor_caption='SENSORES: REVISAR')
    def test_screen_shows_missing_real_and_history_gaps(self):
        ui=Dashboard(Display());data=self.data()
        with patch.object(ui.g,'text',wraps=ui.g.text) as text:
            ui.draw(data,0,'SIN WIFI')
        labels=[c.args[0] for c in text.call_args_list]
        self.assertIn('--',labels)
        self.assertTrue(any('SENSORES' in t for t in labels))
        self.assertFalse(any('DEMO' in t for t in labels))
        history=History()
        for i,value in enumerate((700,None,900,None)):
            item=dict(data,co2=value);history.add(i*5,item)
        ui.draw_trends(history,0)
        self.assertEqual(history.series('co2'),[(0,700),(5,None),(10,900),(15,None)])
    def test_api_freshness_is_measured_and_web_accepts_null(self):
        clock={'local':None,'timezone':'UTC','source':'unset'}
        snap=make_snapshot(self.data(),10000,'not-a-capture',10000,clock,False)
        self.assertEqual(snap['measurements']['age_ms'],200)
        self.assertEqual(snap['measurements']['sample_uptime_ms'],9800)
        self.assertIsNone(snap['measurements']['sample_utc'])
        self.assertIn(b'--',render(snap))
        self.assertNotIn(b'None',render(snap))
        data=self.data();data['field_age_ms']={k:None for k in data['field_age_ms']}
        snap=make_snapshot(data,10000,None,10000,clock,False)
        self.assertIsNone(snap['measurements']['age_ms'])
        self.assertIn(b'--',render(snap))
