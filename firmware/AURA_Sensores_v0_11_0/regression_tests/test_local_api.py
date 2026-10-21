import errno
import json
import unittest
from unittest.mock import patch
import test_firmware
from demo import DemoSource

class Client:
    def __init__(self, chunks=(), short=10000):
        self.chunks=list(chunks);self.short=short;self.output=bytearray();self.closed=False;self.blocking=None
        self.recvs=[];self.sends=[]
    def setblocking(self,value):self.blocking=value
    def recv(self,n):
        self.recvs.append(n)
        if not self.chunks:raise OSError(errno.EAGAIN)
        part=self.chunks.pop(0)
        result=part[:n]
        if len(part)>n:self.chunks.insert(0,part[n:])
        return result
    def send(self,data):
        self.sends.append(len(data))
        n=min(self.short,len(data));self.output.extend(data[:n]);return n
    def close(self):self.closed=True

class Listener(Client):
    def __init__(self):super().__init__();self.pending=[];self.bound=None;self.backlog=None
    def setsockopt(self,*args):pass
    def bind(self,address):self.bound=address
    def listen(self,n):self.backlog=n
    def accept(self):
        if not self.pending:raise OSError(errno.EAGAIN)
        return self.pending.pop(0),('192.0.2.20',40000)

class APITests(unittest.TestCase):
    def setUp(self):
        p=patch('local_api.time.ticks_diff',side_effect=lambda a,b:((a-b+(1<<29))%(1<<30))-(1<<29),create=True)
        p.start();self.addCleanup(p.stop)

    def snap(self):
        from local_api import make_snapshot
        return make_snapshot(DemoSource().read(),1000,None,2000,
                             dict(ready=False,source='unset',timezone='UTC',utc=None,local=None),True)
    def server(self):
        from local_api import LocalAPI
        self.listener=Listener()
        self.api=LocalAPI(self.snap,socket_factory=lambda:self.listener)
        self.api.poll(0,'192.0.2.10')
        return self.api

    def test_snapshot_preserves_capture_time_and_does_not_read_source(self):
        from local_api import make_snapshot, build_response
        source=DemoSource();data=source.read();index=source.index
        clock=dict(ready=True,source='manual',timezone='UTC',utc='2026-10-16T12:00:00Z',local='2026-10-16T12:00:00+00:00')
        snap=make_snapshot(data,1000,None,2000,clock,True)
        self.assertEqual(snap['measurements']['age_ms'],1000)
        self.assertIsNone(snap['measurements']['sample_utc'])
        for path in ('/','/api/measurements','/api/status'):
            reply=build_response(path,snap)
            header,body=reply.split(b'\r\n\r\n',1)
            self.assertIn(b'200 OK',header)
            self.assertIn(('Content-Length: %d'%len(body)).encode(),header)
            self.assertNotIn(b'PASSWORD',reply);self.assertNotIn(b'SSID',reply)
        self.assertEqual(source.index,index)
        self.assertEqual(json.loads(build_response('/api/measurements',snap).split(b'\r\n\r\n')[1])['co2_ppm'],650)

    def test_unknown_path_and_method(self):
        from local_api import parse_request,build_response
        self.assertEqual(parse_request(b'GET /api/status HTTP/1.1\r\nHost: aura\r\n\r\n'),(200,'/api/status'))
        self.assertEqual(parse_request(b'GET /api/status?x=1 HTTP/1.0\r\n\r\n'),(200,'/api/status'))
        self.assertEqual(parse_request(b'POST / HTTP/1.1\r\nHost: aura\r\n\r\n')[0],405)
        self.assertIn(b'404 Not Found',build_response('/favicon.ico',self.snap()))
        for extra in (b'Content-Length: 1\r\n',b'Content-Length: x\r\n',b'Transfer-Encoding: chunked\r\n',
                      b'Content-Length: 0\r\nContent-Length: 1\r\n',b'invalid\r\n'):
            self.assertEqual(parse_request(b'GET / HTTP/1.1\r\nHost: aura\r\n'+extra+b'\r\n')[0],400)

    def test_fragmented_request_short_writes_and_limits(self):
        api=self.server()
        request=b'GET /api/status HTTP/1.1\r\nHost: aura\r\n\r\n'
        client=Client([bytes((v,)) for v in request],short=7)
        self.listener.pending.append(client)
        for now in range(0,1500,5):
            api.poll(now,'192.0.2.10')
            if client.closed:break
        self.assertTrue(client.closed);self.assertEqual(api.client_count,0)
        self.assertTrue(client.output.startswith(b'HTTP/1.1 200 OK'))
        self.assertLessEqual(max(client.recvs),256);self.assertLessEqual(max(client.sends),512)
        self.assertFalse(client.blocking)

    def test_slow_client_deadline_and_busy(self):
        api=self.server();client=Client([b'GET / HTTP/1.1\r\n'])
        self.listener.pending.append(client);api.poll(1,'192.0.2.10')
        api.poll(1000,'192.0.2.10',busy=True)
        self.assertFalse(client.closed)
        api.poll(2001,'192.0.2.10');self.assertTrue(client.closed)
        self.assertEqual(api.client_count,0)

    def test_header_limit_and_two_clients(self):
        api=self.server()
        a=Client([b'G'*1300]);b=Client();c=Client()
        self.listener.pending.extend((a,b,c))
        for now in range(10):api.poll(now,'192.0.2.10')
        self.assertLessEqual(api.client_count,2)
        self.assertIn(b'431 Request Header Fields Too Large',a.output)
        self.assertEqual(self.listener.backlog,2)
        api.close();self.assertTrue(b.closed);self.assertTrue(c.closed)

    def test_rebind_and_bind_failure_cleanup(self):
        from local_api import LocalAPI
        listeners=[]
        def factory():
            listener=Listener();listeners.append(listener);return listener
        api=LocalAPI(self.snap,socket_factory=factory)
        api.poll(0,'192.0.2.10');client=Client();listeners[-1].pending.append(client)
        api.poll(1,'192.0.2.10');api.poll(2,'192.0.2.11')
        self.assertTrue(client.closed);self.assertTrue(listeners[0].closed)
        self.assertEqual(api.url,'http://192.0.2.11:8080')
        api.poll(3,None);self.assertTrue(listeners[-1].closed);self.assertEqual(api.client_count,0)
        bad=Listener()
        with patch.object(bad,'bind',side_effect=OSError):
            broken=LocalAPI(self.snap,socket_factory=lambda:bad)
            broken.poll(0,'192.0.2.10');self.assertTrue(bad.closed);self.assertEqual(broken.state,'error')

    def test_repeated_client_cycles(self):
        api=self.server()
        for i in range(3000):
            client=Client([b'GET /api/measurements HTTP/1.0\r\n\r\n'])
            self.listener.pending.append(client)
            for j in range(8):
                api.poll(i*10+j,'192.0.2.10')
                if client.closed:break
            self.assertTrue(client.closed);self.assertEqual(api.client_count,0)
        api.close();self.assertTrue(self.listener.closed)

    def test_deadline_across_ticks_wrap(self):
        import local_api
        api=self.server();client=Client();self.listener.pending.append(client)
        with patch('local_api.time.ticks_diff',side_effect=lambda a,b:((a-b+(1<<29))%(1<<30))-(1<<29),create=True):
            api.poll((1<<30)-1000,'192.0.2.10')
            api.poll(1001,'192.0.2.10');self.assertTrue(client.closed)
