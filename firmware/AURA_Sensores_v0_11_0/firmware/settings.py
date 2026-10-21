"""Preferencias locales; guardar antes de aplicar. Sin credenciales."""
import json
import os
import config
INTERVALS = (2000, 5000, 10000)
ZONES = ('Europe/Madrid', 'Atlantic/Canary', 'UTC')

class Settings:
    def __init__(self, path='aura_settings.json'):
        self.path = path
        self.interval = config.UPDATE_MS
        self.zone = config.TIMEZONE
        try:
            with open(path) as f:
                data = json.load(f)
            if self.valid(data['interval'], data['zone']):
                self.interval, self.zone = data['interval'], data['zone']
        except (OSError, ValueError, TypeError, KeyError):
            pass

    @staticmethod
    def valid(interval, zone):
        return type(interval) is int and interval in INTERVALS and zone in ZONES

    def save(self, interval, zone):
        if not self.valid(interval, zone):
            return False
        try:
            with open(self.path + '.tmp', 'w') as f:
                json.dump({'interval': interval, 'zone': zone}, f)
                f.flush()
            os.rename(self.path + '.tmp', self.path)
        except OSError:
            return False
        self.interval, self.zone = interval, zone
        return True

    def apply(self):
        config.UPDATE_MS = self.interval
        config.TIMEZONE = self.zone
