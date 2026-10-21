"""HTTP de solo lectura en la LAN; sockets y buffers limitados, sin esperas de red."""
import socket
import time
import errno
import json
import config

REASONS = {200:'OK',400:'Bad Request',404:'Not Found',405:'Method Not Allowed',
           431:'Request Header Fields Too Large',500:'Internal Server Error'}


def make_snapshot(data, captured_uptime_ms, captured_utc, uptime_ms, clock_state, wifi_connected):
    age = max(0,uptime_ms-captured_uptime_ms)
    if 'field_age_ms' in data:
        ages = [a for a in data['field_age_ms'].values() if a is not None]
        age = max(ages) if ages else None
        captured_uptime_ms = max(0,uptime_ms-age) if age is not None else None
        # Independent conversions do not share an exact UTC capture instant.
        captured_utc = None
    return {'measurements': {'co2_ppm':data['co2'], 'temperature_c':data['temperature'],
            'humidity_pct':data['humidity'], 'pressure_hpa':data['pressure'],
            'demo':bool(data.get('demo',True)), 'sample_uptime_ms':captured_uptime_ms,
            'age_ms':age, 'sample_utc':captured_utc,
            'sources':dict(data.get('sources',{})),
            'field_age_ms':dict(data.get('field_age_ms',{})),
            'sensors':data.get('sensors',{})},
            'status': {'firmware':config.FIRMWARE_VERSION, 'uptime_ms':uptime_ms,
            'demo':bool(data.get('demo',True)), 'wifi_connected':bool(wifi_connected),
            'api':{'state':'waiting','url':None}, 'clock':dict(clock_state)}}


def parse_request(header):
    end = header.find(b'\r\n\r\n')
    if end < 0:
        return 0,None
    if end+4 != len(header):
        return 400,None
    lines = header[:end].split(b'\r\n')
    line = lines[0].split(b' ')
    if len(line) != 3 or line[2] not in (b'HTTP/1.0',b'HTTP/1.1'):
        return 400,None
    method,target,version = line
    if not method or any(v < 65 or v > 90 for v in method):
        return 400,None
    if not target.startswith(b'/') or any(v <= 32 or v >= 127 for v in target):
        return 400,None
    seen_length = False
    host = None
    for raw in lines[1:]:
        if b':' not in raw or raw[:1] in (b' ',b'\t'):
            return 400,None
        key,value = raw.split(b':',1)
        key = key.lower()
        value = value.strip()
        if not key or any(v <= 32 or v >= 127 for v in key):
            return 400,None
        if key == b'transfer-encoding':
            return 400,None
        if key == b'content-length':
            if seen_length or not value or any(v < 48 or v > 57 for v in value) or int(value) != 0:
                return 400,None
            seen_length = True
        if key == b'host':
            if host is not None or not value:
                return 400,None
            host = value
    if version == b'HTTP/1.1' and host is None:
        return 400,None
    if method != b'GET':
        return 405,None
    return 200,target.split(b'?',1)[0].decode()


def _response(status, body=None, kind='text/plain; charset=utf-8'):
    if body is None:
        body = REASONS[status].encode()
    extra = 'Allow: GET\r\n' if status == 405 else ''
    head = ('HTTP/1.1 %d %s\r\nContent-Type: %s\r\nContent-Length: %d\r\n'
            'Cache-Control: no-store\r\nConnection: close\r\n%s\r\n' %
            (status,REASONS[status],kind,len(body),extra))
    return head.encode()+body


def _escape(value):
    return str(value).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')


def build_response(path, snapshot):
    if path in ('/api/measurements','/api/status'):
        key = 'measurements' if path == '/api/measurements' else 'status'
        return _response(200,json.dumps(snapshot[key]).encode(),'application/json; charset=utf-8')
    if path != '/':
        return _response(404)
    from web_page import render
    return _response(200,render(snapshot),'text/html; charset=utf-8')


def _would_block(error):
    return bool(error.args) and error.args[0] in (errno.EAGAIN,getattr(errno,'EWOULDBLOCK',errno.EAGAIN))


class LocalAPI:
    def __init__(self, snapshot_fn, enabled=True, port=8080, socket_factory=None):
        self.snapshot_fn = snapshot_fn
        self.enabled = enabled
        self.port = port
        self.factory = socket_factory or (lambda:socket.socket(socket.AF_INET,socket.SOCK_STREAM))
        self.listener = None
        self.clients = [None,None]
        self.ip = None
        self.url = None
        self.state = 'waiting' if enabled else 'disabled'
        self.last_attempt = None

    @property
    def client_count(self):
        return sum(client is not None for client in self.clients)

    def status(self):
        return {'state':self.state,'url':self.url}

    def _drop(self, index):
        client = self.clients[index]
        self.clients[index] = None
        if client is not None:
            try:
                client['socket'].close()
            except OSError:
                pass

    def close(self):
        for index in range(2):
            self._drop(index)
        if self.listener is not None:
            try:
                self.listener.close()
            except OSError:
                pass
        self.listener = None
        self.ip = self.url = None
        self.last_attempt = None
        self.state = 'waiting' if self.enabled else 'disabled'

    def _open(self, now):
        sock = None
        self.last_attempt = now
        try:
            sock = self.factory()
            try:
                sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            except (OSError,AttributeError):
                pass
            sock.setblocking(False)
            sock.bind((self.ip,self.port))
            sock.listen(2)
        except OSError:
            if sock is not None:
                sock.close()
            self.state = 'error'
            return
        self.listener = sock
        self.url = 'http://%s:%d' % (self.ip,self.port)
        self.state = 'ready'

    def _step(self, index):
        client = self.clients[index]
        sock = client['socket']
        try:
            if client['tx'] is not None:
                view = memoryview(client['tx'])
                start = client['sent']
                sent = sock.send(view[start:start+512])
                if not sent:
                    self._drop(index)
                    return
                client['sent'] += sent
                if client['sent'] == len(client['tx']):
                    self._drop(index)
                return
            remaining = 1024-len(client['rx'])
            data = sock.recv(min(256,remaining+1))
            if not data:
                self._drop(index)
                return
            if len(data) > remaining:
                client['tx'] = _response(431)
                client['rx'] = None
                return
            client['rx'].extend(data)
            status,path = parse_request(client['rx'])
            if status:
                if status != 200:
                    client['tx'] = _response(status)
                else:
                    snapshot = self.snapshot_fn()
                    snapshot = dict(snapshot)
                    snapshot['status'] = dict(snapshot['status'])
                    snapshot['status']['api'] = self.status()
                    client['tx'] = build_response(path,snapshot)
                client['rx'] = None
        except OSError as error:
            if not _would_block(error):
                self._drop(index)
        except (ValueError,TypeError,KeyError):
            client['tx'] = _response(400)
            client['rx'] = None

    def poll(self, now_ms, ip_or_none, busy=False):
        if not self.enabled or not ip_or_none:
            self.close()
            return
        if self.ip != ip_or_none:
            self.close()
            self.ip = ip_or_none
        if busy:
            return
        if self.listener is None:
            if self.last_attempt is None or time.ticks_diff(now_ms,self.last_attempt) >= 5000:
                self._open(now_ms)
            if self.listener is None:
                return
        for index,client in enumerate(self.clients):
            if client is not None and time.ticks_diff(now_ms,client['started']) >= 2000:
                self._drop(index)
        if self.client_count < 2:
            peer = None
            try:
                peer,_ = self.listener.accept()
                peer.setblocking(False)
                index = self.clients.index(None)
                self.clients[index] = {'socket':peer,'started':now_ms,'rx':bytearray(), 'tx':None,'sent':0}
            except OSError as error:
                if peer is not None:
                    peer.close()
                if not _would_block(error):
                    old_ip = self.ip
                    self.close()
                    self.ip = old_ip
                    self.state = 'error'
                    self.last_attempt = now_ms
                    return
        for index in range(2):
            if self.clients[index] is not None:
                self._step(index)
