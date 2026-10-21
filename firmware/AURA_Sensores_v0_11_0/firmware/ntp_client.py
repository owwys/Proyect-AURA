"""Consulta NTP simple por UDP. No requiere instalar el modulo ntptime."""
import os
import socket
import struct
import time
from machine import RTC


def decode_reply(reply, token, epoch_year):
    if len(reply) < 48:
        raise OSError('NTP: respuesta incompleta')
    version = (reply[0] >> 3) & 7
    if reply[0] >> 6 == 3 or (reply[0] & 7) != 4 or version not in (3, 4):
        raise OSError('NTP: servidor no sincronizado o respuesta invalida')
    if not 1 <= reply[1] <= 15 or reply[24:32] != token:
        raise OSError('NTP: estrato u origen invalido')
    seconds = struct.unpack('!I', reply[40:44])[0]
    if seconds == 0:
        raise OSError('NTP: fecha vacia')
    # Era posterior al desbordamiento NTP de febrero de 2036.
    if seconds < 3913056000:  # 2024-01-01; este software es posterior.
        seconds += 0x100000000
    if epoch_year == 2000:
        seconds -= 3155673600
    elif epoch_year == 1970:
        seconds -= 2208988800
    else:
        raise ValueError('Epoch no soportado')
    return seconds


def sync(host='pool.ntp.org', timeout=3):
    request = bytearray(48)
    request[0] = 0x23  # NTP version 4, cliente
    token = os.urandom(8)
    request[40:48] = token
    addr = socket.getaddrinfo(host, 123, socket.AF_INET, socket.SOCK_DGRAM)[0][-1]
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.settimeout(timeout)
        sock.connect(addr)
        sock.send(request)
        reply = sock.recv(512)
    finally:
        sock.close()
    seconds = decode_reply(reply, token, time.gmtime(0)[0])
    stamp = time.gmtime(seconds)
    if not 2025 <= stamp[0] <= 2099:
        raise OSError('NTP: fecha fuera del rango admitido')
    RTC().datetime((stamp[0], stamp[1], stamp[2], stamp[6],
                    stamp[3], stamp[4], stamp[5], 0))
    return seconds
