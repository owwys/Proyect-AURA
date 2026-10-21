"""Punto de entrada del primer arranque. Nunca activar un AP abierto como alternativa."""
import os
import binascii

def short_secret(length):
    alphabet="23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    return "".join(alphabet[b & 31] for b in os.urandom(length))

import network
from wifi_store import WiFiStore
from provisioning import SetupSession
from setup_http import SetupServer


class SetupMode:
    def __init__(self,wlan,now):
        self.session=None;self.server=None;self.ap=None;self.error=None;self.key='';self.wifi_key='';self.ssid='';self.notice=None
        try:
            self.wifi_key=short_secret(8)
            self.key=self.wifi_key
            interface=getattr(network,'AP_IF',None)
            if interface is None:interface=network.WLAN.IF_AP
            self.ap=network.WLAN(interface);self.ap.active(False)
            # ESP32 exige modo AP activo para configurar su seguridad.
            # No crear el servidor hasta verificar WPA2.
            self.ap.active(True)
            suffix=binascii.hexlify(wlan.config('mac')[-3:]).decode().upper()
            self.ssid='AURA-'+suffix
            auth=getattr(network,'AUTH_WPA2_PSK',3)
            try:self.ap.config(ssid=self.ssid,security=auth,key=self.wifi_key)
            except (ValueError,TypeError):self.ap.config(essid=self.ssid,authmode=auth,password=self.wifi_key)
            self.ap.ifconfig(('192.168.4.1','255.255.255.0','192.168.4.1','192.168.4.1'))
            try:security=self.ap.config('security')
            except (ValueError,TypeError):security=self.ap.config('authmode')
            if security != auth:raise ValueError('AP sin WPA2')
            self.session=SetupSession(wlan,WiFiStore(),self.ssid,self.key,now)
            self.server=SetupServer(self.session)
        except (OSError,ValueError,TypeError,AttributeError):
            self.error='No se pudo iniciar WPA2';self.close()
    def snapshot(self):
        if self.session:
            status=self.session.status()
            if self.notice:status['notice']=self.notice
            return status
        return {'state':'setup_error','ap_ssid':self.ssid,'ip':None,'error':self.error,'notice':self.notice}
    def skip(self):
        # Omitir dura solo esta ejecucion: RESET/EN no conserva la orden.
        self.close()
        return True

    def poll(self,now):
        if not self.session:return
        self.session.poll(now)
        if not self.session.active:self.close();return
        if self.server:
            try:self.server.poll(now)
            except OSError:self.error='Error de servidor';self.close()
    def close(self):
        if self.session:
            self.session.active=False;self.session.key='';self.session.pending=None
            if self.error:self.session.state='setup_error';self.session.error='setup_server_failed'
        if self.server:
            self.server.close();self.server=None
        if self.ap:
            try:self.ap.active(False)
            except OSError:pass
        self.key='';self.wifi_key=''
