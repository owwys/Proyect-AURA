"""HTTP de configuracion solo para el AP privado, con limites separados de la API de lectura."""
import json
import socket
import errno
from provisioning import diff


def parse_setup_request(raw,key=None):
    end=raw.find(b'\r\n\r\n')
    if end<0:return (431,None,None) if len(raw)>1024 else (0,None,None)
    if end+4>1024:return 431,None,None
    try:
        lines=bytes(raw[:end]).split(b'\r\n');method,path,version=lines[0].split(b' ')
        if version not in (b'HTTP/1.0',b'HTTP/1.1') or method not in (b'GET',b'POST'):return 400,None,None
        headers={}
        for line in lines[1:]:
            name,value=line.split(b':',1);name=name.lower()
            if not name or name in headers or any(c<=32 or c>=127 for c in name):return 400,None,None
            headers[name]=value.strip()
        if b'transfer-encoding' in headers or b'origin' in headers:return 400,None,None
        if version==b'HTTP/1.1' and not headers.get(b'host'):return 400,None,None
        if key is not None:
            auth=headers.get(b'authorization',b'');expected=('Bearer '+key).encode()
            mismatch=len(auth)^len(expected)
            for a,b in zip(auth,expected):mismatch|=a^b
            if not key or mismatch:return 401,None,None
        elif headers.get(b'host') not in (b'192.168.4.1',b'192.168.4.1:8081'):
            return 400,None,None
        length=headers.get(b'content-length',b'0')
        if not length or not all(48<=c<=57 for c in length):return 400,None,None
        length=int(length)
        if length>1024:return 413,None,None
        count=len(raw)-(end+4)
        if count<length:return 0,None,None
        if count!=length:return 400,None,None
        if method==b'GET' and length:return 400,None,None
        if method==b'POST' and headers.get(b'content-type')!=b'application/json':return 400,None,None
        route=path.decode()
        if (method,route) not in ((b'GET','/setup/status'),(b'GET','/setup/networks'),(b'POST','/setup/networks'),(b'POST','/setup/wifi'),(b'POST','/setup/finish')):return 404,None,None
        payload=json.loads(bytes(raw[end+4:]).decode()) if method==b'POST' else None
        return 200,route,payload
    except (ValueError,TypeError,UnicodeError):return 400,None,None


def response(code,data):
    body=json.dumps(data).encode()
    if len(body)>4096:code=500;body=b'{"error":"response_limit"}'
    return ('HTTP/1.1 %d Result\r\nContent-Type: application/json\r\nContent-Length: %d\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n'%(code,len(body))).encode()+body


def blocked(error):return error.args and error.args[0] in (errno.EAGAIN,getattr(errno,'EWOULDBLOCK',errno.EAGAIN))


class SetupServer:
    def __init__(self,session,ip='192.168.4.1',port=8081,factory=None):
        self.session=session;self.clients=[None,None]
        self.sock=(factory or (lambda:socket.socket(socket.AF_INET,socket.SOCK_STREAM)))()
        try:
            self.sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);self.sock.setblocking(False)
            self.sock.bind((ip,port));self.sock.listen(2)
        except Exception:self.sock.close();raise
    def drop(self,i):
        c=self.clients[i];self.clients[i]=None
        if c:
            try:c['socket'].close()
            except OSError:pass
    def close(self):
        for i in range(2):self.drop(i)
        self.sock.close()
    def poll(self,now):
        for i,c in enumerate(self.clients):
            if c and diff(now,c['since'])>=5000:self.drop(i)
        if None in self.clients:
            peer=None
            try:
                peer,address=self.sock.accept()
                parts=address[0].split('.')
                if len(parts)!=4 or parts[:3]!=['192','168','4'] or not parts[3].isdigit() or not 2<=int(parts[3])<=254:
                    peer.close();peer=None
                if peer is not None:peer.setblocking(False)
                if peer is not None:
                    self.clients[self.clients.index(None)]={'socket':peer,'since':now,'raw':bytearray(),'tx':None,'sent':0}
            except OSError as e:
                if peer:peer.close()
                if not blocked(e):raise
        for i,c in enumerate(self.clients):
            if not c:continue
            try:
                if c['tx'] is not None:
                    n=c['socket'].send(memoryview(c['tx'])[c['sent']:c['sent']+512])
                    if not n:self.drop(i);continue
                    c['sent']+=n
                    if c['sent']==len(c['tx']):self.drop(i)
                    continue
                chunk=c['socket'].recv(256)
                if not chunk:self.drop(i);continue
                c['raw'].extend(chunk)
                code,path,payload=parse_setup_request(c['raw'])
                if code==0:continue
                data={'error':'request_rejected'}
                if code==200:
                    if path=='/setup/status':data=self.session.status()
                    elif path=='/setup/networks':
                        if payload not in (None,{}):code=400
                        else:data={'networks':self.session.networks(now,force=payload is not None)}
                    elif path=='/setup/wifi':code=self.session.submit(payload,now);data=self.session.status()
                    elif payload != {}:code=400
                    elif self.session.finish(now):data={'ok':True}
                    else:code=409
                c['raw']=None;c['tx']=response(code,data)
            except OSError as e:
                if not blocked(e):self.drop(i)
            except (ValueError,TypeError,KeyError):self.drop(i)
