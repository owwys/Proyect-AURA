"""Sesion de alta: secretos efimeros, ensayo antes de guardar y tiempos acotados."""
from wifi_store import validate


def diff(a,b):
    import time
    fn=getattr(time,'ticks_diff',None)
    return fn(a,b) if fn else a-b


class SetupSession:
    def __init__(self,wlan,store,ssid,key,now):
        self.wlan,self.store,self.ssid,self.key=wlan,store,ssid,key
        self.started=now;self.active=True;self.state='ready';self.error=None
        self.ip=None;self.pending=None;self.request_id=None;self.attempt=None;self.completed=None;self.close_since=None
        self.cache=[];self.scanned=None
    def status(self):
        return {'protocol_version':1,'ap_ssid':self.ssid,'state':self.state,'ip':self.ip,'error':self.error,'request_id':self.request_id}
    def submit(self,payload,now):
        if not self.active:return 410
        if type(payload) is not dict or set(payload) != {'ssid','password','open_network','request_id'}:return 400
        try:validate(payload['ssid'],payload['password'],payload['open_network'])
        except (ValueError,TypeError):return 400
        rid=payload['request_id']
        if type(rid) is not str or not 16 <= len(rid) <= 64 or not all(c in '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ-' for c in rid):return 400
        if rid == self.request_id:return 200 if self.state=='connected' else 202
        if self.state in ('connecting','connected'):return 409
        self.request_id=rid;self.error=None;self.ip=None
        self.pending=(payload['ssid'],payload['password'],payload['open_network'])
        self.state='connecting';self.attempt=now
        try:
            self.wlan.active(True);self.wlan.disconnect();self.wlan.connect(*self.pending[:2])
        except OSError:self._failed('connection_failed')
        return 202
    def _failed(self,error):
        self.state='failed';self.error=error;self.pending=None
        try:self.wlan.disconnect()
        except OSError:pass
    def networks(self,now,force=False):
        if not self.active or self.state=='connecting':return self.cache
        if self.scanned is not None and diff(now,self.scanned)<(5000 if force else 30000):return self.cache
        self.scanned=now;found={}
        try:
            self.wlan.active(True)
            for raw,_,channel,rssi,security,hidden in self.wlan.scan():
                try:ssid=raw.decode('utf-8')
                except (ValueError,UnicodeError):continue
                if not ssid or security not in (0,2,3,4):continue
                item={'ssid':ssid,'rssi':rssi,'open_network':security==0}
                if ssid not in found or rssi>found[ssid]['rssi']:found[ssid]=item
            self.cache=sorted(found.values(),key=lambda x:x['rssi'],reverse=True)[:20]
        except OSError:pass
        return self.cache
    def finish(self,now):
        if self.state!='connected':return False
        self.close_since=now;return True
    def poll(self,now):
        if not self.active:return
        if diff(now,self.started)>=600000 or (self.close_since is not None and diff(now,self.close_since)>=2000) or (self.completed is not None and diff(now,self.completed)>=10000):
            self.active=False;self.pending=None;self.key=''
            if self.state!='connected':self.state='expired'
            return
        if self.state!='connecting':return
        try:
            if self.wlan.isconnected() and self.wlan.config('ssid')==self.pending[0]:
                ip=self.wlan.ifconfig()[0]
                if not ip or ip=='0.0.0.0':return
                try:self.store.save(*self.pending)
                except OSError:self._failed('storage_failed');return
                self.ip=ip;self.state='connected';self.pending=None;self.completed=now
            elif self.wlan.status()<0 or diff(now,self.attempt)>=20000:self._failed('connection_failed')
        except OSError:self._failed('connection_failed')
