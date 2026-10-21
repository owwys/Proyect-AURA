"""RTC en UTC; conversion local al dibujar, sin modificar el reloj dos veces."""
import time
import config


def _last_sunday(year, month):
    # Calendario gregoriano, marzo u octubre. Domingo=0.
    term = 2 if month == 3 else 6
    weekday = (year + year // 4 - year // 100 + year // 400 + term + 31) % 7
    return 31 - weekday


def offset_seconds(utc_seconds, zone=None):
    if zone is None:
        zone = config.TIMEZONE
    if zone == 'UTC':
        return 0
    if zone not in ('Europe/Madrid', 'Atlantic/Canary'):
        raise ValueError('Zona no admitida: ' + zone)
    utc = time.gmtime(utc_seconds)
    year = utc[0]
    # Regla europea: ultimo domingo de marzo/octubre, 01:00 UTC.
    start = (3, _last_sunday(year, 3), 1)
    end = (10, _last_sunday(year, 10), 1)
    summer = start <= (utc[1], utc[2], utc[3]) < end
    base = 3600 if zone == 'Europe/Madrid' else 0
    return base + (3600 if summer else 0)


def localtime(utc_seconds=None):
    if utc_seconds is None:
        utc_seconds = time.time()
    return time.gmtime(utc_seconds + offset_seconds(utc_seconds))


def month_days(year, month):
    if month == 2:
        return 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28
    return 30 if month in (4, 6, 9, 11) else 31


def validate_parts(parts, first=2025, last=2099):
    if len(parts) != 6 or any(type(v) is not int for v in parts):
        raise ValueError('Fecha no valida')
    y, m, d, h, minute, second = parts
    if not first <= y <= last or not 1 <= m <= 12:
        raise ValueError('Fecha fuera de rango')
    if not 1 <= d <= month_days(y, m) or not 0 <= h < 24 or not 0 <= minute < 60 or not 0 <= second < 60:
        raise ValueError('Fecha no valida')


def calendar_seconds(parts, epoch_year=None):
    # Aritmetica UTC independiente de la zona del ordenador o del port.
    if epoch_year is None:
        epoch_year = time.gmtime(0)[0]
    if epoch_year not in (1970, 2000):
        raise ValueError('Epoch no soportado')
    y, m, d, h, minute, second = parts
    days = 0
    for year in range(epoch_year, y):
        days += 366 if month_days(year, 2) == 29 else 365
    for month in range(1, m):
        days += month_days(y, month)
    return ((days+d-1)*24+h)*3600+minute*60+second


def utc_candidates(parts, zone):
    validate_parts(parts)
    if zone == 'UTC':
        offsets = (0,)
    elif zone == 'Europe/Madrid':
        offsets = (3600, 7200)
    elif zone == 'Atlantic/Canary':
        offsets = (0, 3600)
    else:
        raise ValueError('Zona no admitida')
    nominal = calendar_seconds(parts)
    candidates = []
    for offset in offsets:
        seconds = nominal-offset
        if offset_seconds(seconds, zone) == offset and tuple(time.gmtime(seconds+offset)[:6]) == tuple(parts):
            candidates.append(seconds)
    return tuple(sorted(candidates))
