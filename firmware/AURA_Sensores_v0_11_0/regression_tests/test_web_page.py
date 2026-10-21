import unittest
from html.parser import HTMLParser
import test_firmware
import test_local_api as api_tests

class PageParser(HTMLParser):
    def __init__(self):
        super().__init__();self.ids=[];self.external=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        for key in ('href','src'):
            if a.get(key,'').startswith(('http:','https:','//')):self.external.append(a[key])

class WebTests(unittest.TestCase):
    def test_offline_fallback_accessibility_and_size(self):
        from local_api import build_response
        snap=api_tests.APITests().snap()
        reply=build_response('/',snap);head,body=reply.split(b'\r\n\r\n',1)
        text=body.decode();parser=PageParser();parser.feed(text)
        self.assertIn('id="co2"',text)
        self.assertIn('650',text)
        self.assertIn('Datos simulados',text)
        self.assertIn('Sin ajustar',text)
        self.assertIn('aria-live="polite"',text)
        self.assertIn('<noscript>',text)
        self.assertIn('prefers-reduced-motion',text)
        self.assertLessEqual(len(body),14000)
        self.assertEqual(parser.external,[])
        self.assertEqual(len(parser.ids),len(set(parser.ids)))
        self.assertIn(('Content-Length: %d'%len(body)).encode(),head)

    def test_untrusted_snapshot_is_escaped(self):
        from local_api import build_response
        snap=api_tests.APITests().snap()
        snap['measurements']['co2_ppm']='<script>alert(1)</script>'
        body=build_response('/',snap).split(b'\r\n\r\n',1)[1].decode()
        self.assertNotIn('<script>alert(1)</script>',body)
        self.assertIn('&lt;script&gt;',body)

    def test_complete_page_fits_existing_socket_deadline(self):
        case=api_tests.APITests();case.setUp()
        try:
            api=case.server();client=api_tests.Client([b'GET / HTTP/1.0\r\n\r\n'])
            case.listener.pending.append(client)
            for now in range(0,1800,20):
                api.poll(now,'192.0.2.10')
                if client.closed:break
            self.assertTrue(client.closed)
            head,body=bytes(client.output).split(b'\r\n\r\n',1)
            self.assertIn(('Content-Length: %d'%len(body)).encode(),head)
            self.assertTrue(body.endswith(b'</html>'))
        finally:case.doCleanups()
