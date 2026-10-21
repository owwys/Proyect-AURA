"""Hora valida independiente de Wi-Fi. El RTC almacena UTC, nunca una hora congelada en flash."""
import time
import config
from local_clock import utc_candidates, calendar_seconds, offset_seconds, validate_parts

SOURCES = {'unset': 'SIN AJUSTAR', 'manual': 'MANUAL', 'ntp': 'NTP', 'retained': 'CONSERVADA'}


class AmbiguousTimeError(ValueError):
    def __init__(self, candidates):
        self.candidates = candidates
        super().__init__('Elegir verano/invierno')


def iso(seconds, offset=None):
    stamp = time.gmtime(seconds+(offset or 0))
    text = '%04d-%02d-%02dT%02d:%02d:%02d' % tuple(stamp[:6])
    if offset is None:
        return text+'Z'
    return text+('%s%02d:%02d' % ('+' if offset >= 0 else '-', abs(offset)//3600, abs(offset)%3600//60))


class ClockService:
    def __init__(self, rtc=None):
        if rtc is None:
            from machine import RTC
            rtc = RTC()
        self.rtc = rtc
        self.ready = False
        self.source = 'unset'
        self.retention_available = False
        try:
            if rtc.memory() in (b'AURA08:manual', b'AURA08:ntp', b'AURA08:retained'):
                self._read_utc()
                self.ready = True
                self.source = 'retained'
                self.retention_available = True
        except (OSError, ValueError, TypeError, AttributeError, IndexError):
            pass

    def _read_utc(self):
        stamp = self.rtc.datetime()
        parts = tuple(stamp[:3])+tuple(stamp[4:7])
        validate_parts(parts, 2024, 2100)
        return calendar_seconds(parts)

    def _remember(self):
        self.retention_available = False
        try:
            self.rtc.memory(('AURA08:'+self.source).encode())
            self.retention_available = True
        except (OSError, ValueError, TypeError, AttributeError):
            pass

    def set_local(self, parts, zone, fold=None):
        if len(parts) != 5 or fold not in (None, 'summer', 'winter'):
            raise ValueError('Fecha no valida')
        candidates = utc_candidates(tuple(parts)+(0,), zone)
        if not candidates:
            raise ValueError('Hora local inexistente')
        if len(candidates) == 2 and fold is None:
            raise AmbiguousTimeError(candidates)
        seconds = candidates[-1] if len(candidates) == 2 and fold == 'winter' else candidates[0]
        stamp = time.gmtime(seconds)
        self.rtc.datetime((stamp[0], stamp[1], stamp[2], stamp[6], stamp[3], stamp[4], 0, 0))
        self.ready = True
        self.source = 'manual'
        self._remember()
        return seconds

    def mark_ntp(self, seconds):
        # ntp_client.sync ya ha escrito el RTC antes de notificar el exito.
        self.ready = True
        self.source = 'ntp'
        self._remember()

    def snapshot(self):
        seconds = None
        if self.ready:
            try:
                seconds = self._read_utc()
            except (OSError, ValueError, TypeError, IndexError):
                self.ready = False
                self.source = 'unset'
        offset = offset_seconds(seconds, config.TIMEZONE) if seconds is not None else None
        return {'ready': self.ready, 'source': self.source, 'timezone': config.TIMEZONE,
                'utc': iso(seconds) if seconds is not None else None,
                'local': iso(seconds, offset) if seconds is not None else None}
