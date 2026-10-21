"""Credenciales privadas; nunca generar codigo Python a partir de datos de la app."""
import json
import os


def validate(ssid,password,open_network):
    if type(ssid) is not str or not 1 <= len(ssid.encode()) <= 32 or '\x00' in ssid:
        raise ValueError('SSID no valido')
    if type(password) is not str or type(open_network) is not bool or '\x00' in password:
        raise ValueError('Clave no valida')
    if open_network:
        if password:raise ValueError('Red abierta con clave')
    elif not (8 <= len(password.encode()) <= 63 or (len(password)==64 and all(c in '0123456789abcdefABCDEF' for c in password))):
        raise ValueError('Clave WPA no valida')


class WiFiStore:
    def __init__(self,path='wifi_settings.json'):self.path=path
    def load(self):
        try:
            with open(self.path) as f:data=json.load(f)
            validate(data['ssid'],data['password'],data['open_network'])
            return data['ssid'],data['password']
        except (OSError,ValueError,KeyError,TypeError):return None
    def save(self,ssid,password,open_network):
        validate(ssid,password,open_network)
        temporary=self.path+'.tmp'
        try:
            with open(temporary,'w') as f:json.dump({'ssid':ssid,'password':password,'open_network':open_network},f)
            # FAT/LittleFS on ESP32 support rename over the previous file. Never remove it first.
            os.rename(temporary,self.path)
        except OSError:
            try:os.remove(temporary)
            except OSError:pass
            raise

    def clear(self,legacy_path='wifi_config.py'):
        # Preparar ambos archivos antes de borrar: si falla, conservar el JSON anterior.
        temporary=self.path+'.tmp';legacy_temporary=legacy_path+'.tmp'
        try:
            with open(temporary,'w') as f:json.dump({},f)
            with open(legacy_temporary,'w') as f:f.write("SSID = ''\nPASSWORD = ''\n")
            os.rename(legacy_temporary,legacy_path)
            os.rename(temporary,self.path)
        except OSError:
            for path in (temporary,legacy_temporary):
                try:os.remove(path)
                except OSError:pass
            raise
