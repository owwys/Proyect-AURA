import unittest,tempfile,os,json
from pathlib import Path
import test_firmware
from test_local_api import Listener as BaseListener
class APListener(BaseListener):
    def accept(self):
        peer,_=super().accept()
        return peer,('192.168.4.2',40000)

class WLAN:
    def __init__(self):self.connected=False;self.ssid='';self.state=1
    def disconnect(self):self.connected=False
    def active(self,value):pass
    def connect(self,ssid,password):self.ssid=ssid
    def isconnected(self):return self.connected
    def config(self,key):return self.ssid
    def status(self):return self.state
    def ifconfig(self):return ('192.168.1.60','','','')
    def scan(self):return [(b'Casa',b'',1,-45,3,False),(b'Casa',b'',2,-60,3,False),(b'Publica',b'',6,-70,0,False)]

class ProvisioningTests(unittest.TestCase):
    def test_atomic_store_and_validation(self):
        from wifi_store import WiFiStore
        with tempfile.TemporaryDirectory() as folder:
            path=str(Path(folder)/'wifi.json');s=WiFiStore(path)
            self.assertIsNone(s.load());s.save('Casa','12345678',False)
            self.assertEqual(s.load(),('Casa','12345678'))
            for args in [('', '12345678',False),('x'*33,'12345678',False),('Casa','short',False),('Casa','secret',True)]:
                with self.assertRaises(ValueError):s.save(*args)
            self.assertEqual(s.load(),('Casa','12345678'))
    def test_store_failure_preserves_existing(self):
        from wifi_store import WiFiStore
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            s=WiFiStore(str(Path(folder)/'wifi.json'));s.save('Antes','abcdefgh',False)
            with patch('wifi_store.os.rename',side_effect=OSError):
                with self.assertRaises(OSError):s.save('Otra','12345678',False)
            self.assertEqual(s.load(),('Antes','abcdefgh'))
    def test_only_save_after_connected_idempotency_and_finish(self):
        from provisioning import SetupSession
        class Store:
            calls=[]
            def save(self,*a):self.calls.append(a)
        store=Store();w=WLAN();s=SetupSession(w,store,'AURA-123456','a'*20,0)
        p={'ssid':'Casa','password':'12345678','open_network':False,'request_id':'request-1234567890'}
        self.assertEqual(s.submit(p,0),202);self.assertEqual(s.submit(p,1),202);self.assertFalse(store.calls)
        s.poll(1000);self.assertFalse(store.calls)
        w.connected=True;s.poll(2000);self.assertEqual(store.calls,[('Casa','12345678',False)]);self.assertEqual(s.status()['ip'],'192.168.1.60')
        self.assertEqual(s.submit(p,3000),200);s.finish(3000);s.poll(5000);self.assertFalse(s.active)
    def test_failure_timeout_expiry_and_scan(self):
        from provisioning import SetupSession
        w=WLAN();s=SetupSession(w,None,'AURA-123456','a'*20,0)
        self.assertEqual(len(s.networks(0)),2)
        p={'ssid':'Casa','password':'12345678','open_network':False,'request_id':'request-1234567890'}
        s.submit(p,0);w.state=-3;s.poll(1000);self.assertEqual(s.state,'failed')
        s.submit(dict(p,request_id='request-1234567891'),2000);w.state=1;s.poll(22000);self.assertEqual(s.state,'failed')
        s.poll(600000);self.assertFalse(s.active)
    def test_parser_limits_auth_and_fragmented_body(self):
        from setup_http import parse_setup_request
        key='a'*20;body=json.dumps({'ssid':'Casa','password':'12345678','open_network':False,'request_id':'r'*20}).encode()
        header=b'POST /setup/wifi HTTP/1.1\r\nHost: aura\r\nAuthorization: Bearer '+key.encode()+b'\r\nContent-Length: '+str(len(body)).encode()+b'\r\nContent-Type: application/json\r\n\r\n'
        self.assertEqual(parse_setup_request(header,key)[0],0)
        self.assertEqual(parse_setup_request(header+body,key)[0],200)
        self.assertEqual(parse_setup_request(header+body,'b'*20)[0],401)
        self.assertEqual(parse_setup_request(header+body+b'x',key)[0],400)
        self.assertEqual(parse_setup_request(b'G'*1025,key)[0],431)
        self.assertEqual(parse_setup_request(header.replace(b'Content-Length:',b'Transfer-Encoding:' )+body,key)[0],400)

class APProtectionTests(unittest.TestCase):
    def test_ap_requires_verified_wpa2_and_rotates_key(self):
        import test_connectivity
        import setup_mode
        from unittest.mock import patch,Mock
        class AP:
            def __init__(self,secure=True):self.secure=secure;self.security=None;self.activations=[];self.enabled=False
            def active(self,v):self.activations.append(v);self.enabled=v
            def config(self,key=None,**kw):
                if kw:
                    if not self.enabled:raise OSError('Wifi Invalid Mode')
                    self.security=kw.get('security',kw.get('authmode'))
                return self.security if self.secure else 0
            def ifconfig(self,v):pass
        class Station(WLAN):
            def config(self,key):return b'123456' if key=='mac' else self.ssid
        ap=AP();net=type('Net',(),{'AP_IF':1,'AUTH_WPA2_PSK':3,'WLAN':lambda _,i:ap})()
        with patch.object(setup_mode,'network',net),patch.object(setup_mode,'SetupServer',return_value=Mock()):
            mode=setup_mode.SetupMode(Station(),0)
            self.assertEqual(ap.activations,[False,True]);self.assertEqual(len(mode.key),8);self.assertEqual(len(mode.wifi_key),8);self.assertEqual(mode.key,mode.wifi_key);first=mode.key
            mode.close();mode2=setup_mode.SetupMode(Station(),0);self.assertNotEqual(first,mode2.key)
            mode2.session.state='connected';mode2.session.completed=0
            mode2.poll(9999);self.assertTrue(ap.activations[-1])
            mode2.poll(10000);self.assertFalse(ap.activations[-1]);self.assertIsNone(mode2.server)
            mode2.close()
        bad=AP(False);net.WLAN=lambda i:bad
        with patch.object(setup_mode,'network',net),patch.object(setup_mode,'SetupServer') as server:
            mode=setup_mode.SetupMode(Station(),0)
            self.assertFalse(bad.enabled);self.assertEqual(mode.key,'');server.assert_not_called()

    def test_setup_server_fragmentation_auth_no_secret_and_cleanup(self):
        from setup_http import SetupServer
        from provisioning import SetupSession
        from test_local_api import Client
        Listener=APListener
        session=SetupSession(WLAN(),None,'AURA-123456','a'*20,0)
        listener=Listener();server=SetupServer(session,factory=lambda:listener)
        request=b'GET /setup/status HTTP/1.1\r\nHost: 192.168.4.1:8081\r\nAuthorization: Bearer '+b'a'*20+b'\r\n\r\n'
        client=Client([bytes((v,)) for v in request],short=7);listener.pending.append(client)
        for now in range(0,4000,5):
            server.poll(now)
            if client.closed:break
        self.assertTrue(client.closed);self.assertIn(b'200 Result',client.output);self.assertNotIn(b'a'*20,client.output)
        self.assertLessEqual(max(client.recvs),256);self.assertLessEqual(max(client.sends),512)
        waiting=Client();listener.pending.append(waiting);server.poll(4001);server.poll(9001);self.assertTrue(waiting.closed)
        server.close();self.assertTrue(listener.closed)

class ShortSetupTests(unittest.TestCase):
    def test_forced_refresh_rescans_after_five_seconds(self):
        from provisioning import SetupSession
        wlan=WLAN();calls=[]
        wlan.scan=lambda:calls.append(1) or [(b'Casa',None,1,-50,3,False)]
        session=SetupSession(wlan,None,'AURA-123456','ABC234',0)
        session.networks(0);session.networks(1000,force=True)
        self.assertEqual(len(calls),1)
        session.networks(5000,force=True);self.assertEqual(len(calls),2)
        session.networks(6000);self.assertEqual(len(calls),2)

    def test_refresh_post_requires_auth_and_json(self):
        from setup_http import parse_setup_request
        raw=b'POST /setup/networks HTTP/1.1\r\nHost: aura\r\nAuthorization: Bearer ABC234\r\nContent-Type: application/json\r\nContent-Length: 2\r\n\r\n{}'
        self.assertEqual(parse_setup_request(raw,'ABC234'),(200,'/setup/networks',{}))
        self.assertEqual(parse_setup_request(raw,'WRONG2')[0],401)

    def test_setup_only_accepts_clients_on_temporary_network_without_code(self):
        from setup_http import SetupServer
        from provisioning import SetupSession
        from test_local_api import Client
        session=SetupSession(WLAN(),None,'AURA-123456','ABCD2345',0)
        raw=b'GET /setup/status HTTP/1.1\r\nHost: 192.168.4.1:8081\r\n\r\n'
        for listener,accepted in ((APListener(),True),(BaseListener(),False)):
            client=Client([raw]);listener.pending.append(client)
            server=SetupServer(session,factory=lambda:listener)
            for now in range(100):server.poll(now)
            self.assertEqual(b'200 Result' in client.output,accepted)
            self.assertTrue(client.closed)
            server.close()

    def test_success_closes_after_ten_seconds(self):
        from provisioning import SetupSession
        from unittest.mock import Mock
        wlan=WLAN();store=Mock();session=SetupSession(wlan,store,'AURA-123456','ABCD2345',0)
        session.submit({'ssid':'Casa','password':'12345678','open_network':False,'request_id':'r'*20},0)
        wlan.connected=True;session.poll(100)
        self.assertEqual(session.state,'connected')
        session.poll(10099);self.assertTrue(session.active)
        session.poll(10100);self.assertFalse(session.active)

class LegacyConfigOptionalTests(unittest.TestCase):
    def test_absent_legacy_wifi_file_enters_setup(self):
        import builtins
        import test_connectivity
        from unittest.mock import patch
        from pathlib import Path
        real_import=builtins.__import__
        def fake_import(name,*args,**kwargs):
            if name=='wifi_config':raise ImportError('missing legacy config')
            return real_import(name,*args,**kwargs)
        ns={}
        with patch('builtins.__import__',side_effect=fake_import):
            exec((Path(__file__).resolve().parents[1]/'firmware/connectivity.py').read_text(),ns)
        with patch('time.ticks_ms',return_value=0,create=True),patch('wifi_store.WiFiStore.load',return_value=None):
            link=ns['Connectivity']()
        self.assertTrue(link.setup_needed)
        self.assertFalse(link.enabled)
