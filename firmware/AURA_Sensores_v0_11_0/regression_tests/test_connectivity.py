"""Pruebas sin red real: calendario, paquetes NTP y reintentos Wi-Fi."""
import calendar
import datetime
import struct
import sys
import types
import unittest
from unittest.mock import patch, MagicMock
import test_firmware  # Proporciona los sustitutos de machine y framebuf.
import config
import wifi_config
import local_clock
sys.modules['machine'].RTC = MagicMock()
import ntp_client


class FakeWLAN:
    def __init__(self, interface):
        self.connected = False
        self.calls = 0
        self.state = 1
    def active(self, value):
        pass
    def config(self, **kwargs):
        pass
    def connect(self, ssid, password):
        self.calls += 1
    def disconnect(self):
        self.connected = False
    def isconnected(self):
        return self.connected
    def status(self):
        return self.state
    def ifconfig(self):
        return ('192.0.2.1', '', '', '')


sys.modules['network'] = types.SimpleNamespace(STA_IF=0, WLAN=FakeWLAN)
import connectivity


def utc(year, month, day, hour=0, minute=0, second=0):
    return calendar.timegm((year, month, day, hour, minute, second))


class CalendarTests(unittest.TestCase):
    def test_dst_edges_madrid_and_canary(self):
        for stamp, madrid, canary in (
            (utc(2026, 3, 29, 0, 59, 59), '01:59', '00:59'),
            (utc(2026, 3, 29, 1), '03:00', '02:00'),
            (utc(2026, 10, 25, 0, 59, 59), '02:59', '01:59'),
            (utc(2026, 10, 25, 1), '02:00', '01:00'),
        ):
            for zone, expected in (('Europe/Madrid', madrid), ('Atlantic/Canary', canary)):
                with patch.object(config, 'TIMEZONE', zone):
                    t = local_clock.localtime(stamp)
                    self.assertEqual('%02d:%02d' % (t[3], t[4]), expected)
        self.assertEqual(local_clock.offset_seconds(utc(2026, 1, 1), 'UTC'), 0)

    def test_last_sunday_calendar_and_date_rollover(self):
        for year in range(2025, 2032):
            for month in (3, 10):
                day = local_clock._last_sunday(year, month)
                self.assertEqual(datetime.date(year, month, day).weekday(), 6)
                self.assertTrue(25 <= day <= 31)
        with patch.object(config, 'TIMEZONE', 'Europe/Madrid'):
            self.assertEqual(local_clock.localtime(utc(2026, 12, 31, 23, 30))[:5],
                             (2027, 1, 1, 0, 30))


class NTPTests(unittest.TestCase):
    def reply(self, stamp):
        msg = bytearray(48)
        msg[0] = 0x24
        msg[1] = 2
        msg[24:32] = b'12345678'
        msg[40:44] = struct.pack('!I', (stamp + 2208988800) & 0xffffffff)
        return msg

    def test_epochs_and_2036_wrap(self):
        for year in (2026, 2037):
            stamp = utc(year, 10, 15)
            reply = self.reply(stamp)
            self.assertEqual(ntp_client.decode_reply(reply, b'12345678', 1970), stamp)
            self.assertEqual(ntp_client.decode_reply(reply, b'12345678', 2000), stamp - 946684800)

    def test_reject_short_unsynced_wrong_origin_and_stratum(self):
        msg = self.reply(utc(2026, 10, 15))
        cases = [msg[:40]]
        for index, value in ((0, 0xe4), (0, 0x23), (1, 0), (24, 0)):
            copy = bytearray(msg)
            copy[index] = value
            cases.append(copy)
        for bad in cases:
            with self.assertRaises(OSError):
                ntp_client.decode_reply(bad, b'12345678', 1970)

    def test_socket_closed_and_rtc_utc(self):
        stamp = utc(2026, 10, 15, 19, 8)
        sock = MagicMock()
        sock.recv.return_value = self.reply(stamp)
        rtc = MagicMock()
        with patch.object(ntp_client.socket, 'socket', return_value=sock), \
             patch.object(ntp_client.socket, 'getaddrinfo', return_value=[(0, 0, 0, '', ('192.0.2.2', 123))]), \
             patch.object(ntp_client.os, 'urandom', return_value=b'12345678'), \
             patch.object(ntp_client, 'RTC', return_value=rtc):
            self.assertEqual(ntp_client.sync(), stamp)
            rtc.datetime.assert_called_once_with((2026, 10, 15, 3, 19, 8, 0, 0))
            sock.close.assert_called_once()
            sock.recv.side_effect = OSError('timeout')
            with self.assertRaises(OSError):
                ntp_client.sync()
            self.assertEqual(sock.close.call_count, 2)


class ConnectivityTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.patches = [
            patch.object(wifi_config, 'SSID', 'red_de_prueba'),
            patch.object(wifi_config, 'PASSWORD', 'solo_simulada'),
            patch.object(connectivity.time, 'ticks_ms', side_effect=lambda: self.now, create=True),
            patch.object(connectivity.time, 'ticks_add', side_effect=lambda x, y: (x+y) % (1 << 30), create=True),
            patch.object(connectivity.time, 'ticks_diff', side_effect=lambda x, y: ((x-y+(1 << 29)) % (1 << 30))-(1 << 29), create=True),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def test_wifi_timeout_retry_and_sync(self):
        link = connectivity.Connectivity()
        link.poll()
        self.assertEqual(link.caption(), 'WIFI...')
        self.now = 15000
        link.poll()
        self.assertEqual(link.caption(), 'WIFI OFF')
        self.now = 44999
        link.poll()
        self.assertEqual(link.wlan.calls, 1)
        self.now = 45000
        link.poll()
        self.assertEqual(link.wlan.calls, 2)
        link.wlan.connected = True
        with patch.object(ntp_client, 'sync') as sync:
            link.poll()
            self.assertTrue(link.synced)
            self.assertEqual(link.caption(), 'WIFI OK / NTP OK')
            link.poll()
            self.assertEqual(sync.call_count, 1)
            self.now += config.NTP_INTERVAL_MS
            link.poll()
            self.assertEqual(sync.call_count, 2)

    def test_bad_password_and_ntp_failure_retry(self):
        link = connectivity.Connectivity()
        link.poll()
        link.wlan.state = -3
        link.poll()
        self.assertEqual(link.caption(), 'WIFI OFF')
        link.wlan.connected = True
        with patch.object(ntp_client, 'sync', side_effect=OSError('timeout')) as sync:
            link.poll()
            self.assertFalse(link.synced)
            self.assertEqual(link.caption(), 'WIFI OK / SIN HORA')
            self.now = 59999
            link.poll()
            self.assertEqual(sync.call_count, 1)
            self.now = 60000
            link.poll()
            self.assertEqual(sync.call_count, 2)
        with patch.object(ntp_client, 'sync'):
            self.now = 120000
            link.poll()
        link.wlan.connected = False
        self.assertEqual(link.caption(), 'WIFI OFF / RTC OK')

    def test_without_credentials_no_connection(self):
        with patch.object(wifi_config, 'SSID', ''):
            link = connectivity.Connectivity()
            link.poll()
            self.assertEqual(link.wlan.calls, 0)
            self.assertEqual(link.caption(), 'SIN WIFI')

    def test_retry_across_ticks_wrap(self):
        self.now = (1 << 30) - 20000
        link = connectivity.Connectivity()
        link.poll()
        self.now += 15000
        link.poll()
        self.now = 24999
        link.poll()
        self.assertEqual(link.wlan.calls, 1)
        self.now = 25000
        link.poll()
        self.assertEqual(link.wlan.calls, 2)


if __name__ == '__main__':
    unittest.main()
