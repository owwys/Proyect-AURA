import calendar
import datetime
import unittest
from unittest.mock import patch
import test_firmware
import local_clock
import config

class FakeRTC:
    def __init__(self):
        self.stamp = (2000,1,1,5,0,0,0,0)
        self.meta = b''
        self.fail = False
        self.fail_memory = False
    def datetime(self, stamp=None):
        if stamp is not None:
            if self.fail: raise OSError('RTC fallo')
            self.stamp = stamp
        return self.stamp
    def memory(self, value=None):
        if self.fail_memory: raise OSError('Memoria RTC')
        if value is not None: self.meta = value
        return self.meta

class ClockTests(unittest.TestCase):
    def setUp(self):
        p=patch.object(config,'TIMEZONE','Europe/Madrid');p.start();self.addCleanup(p.stop)

    def test_calendar_validation_and_epoch(self):
        from local_clock import utc_candidates, calendar_seconds
        self.assertEqual(utc_candidates((2026,1,15,12,0,0),'UTC'),(1768478400,))
        utc_candidates((2028,2,29,12,0,0),'UTC')
        for parts in ((2027,2,29,0,0,0),(2026,4,31,0,0,0),(2024,1,1,0,0,0),
                      (2100,1,1,0,0,0),(2026,1,1,24,0,0),(2026,1,1,0,60,0)):
            with self.assertRaises(ValueError): utc_candidates(parts,'UTC')
        self.assertEqual(calendar_seconds((2026,1,15,12,0,0),2000),821793600)
        self.assertEqual(calendar_seconds((2026,1,15,12,0,0),1970),1768478400)

    def test_gap_and_ambiguous_hour(self):
        from local_clock import utc_candidates
        self.assertEqual(utc_candidates((2026,3,29,2,30,0),'Europe/Madrid'),())
        self.assertEqual(utc_candidates((2026,10,25,2,30,0),'Europe/Madrid'),
                         (1792888200,1792891800))
        self.assertEqual(len(utc_candidates((2026,10,25,1,30,0),'Atlantic/Canary')),2)
        self.assertEqual(utc_candidates((2026,3,29,1,30,0),'Atlantic/Canary'),())

    def test_local_year_boundary_roundtrip(self):
        from clock_service import ClockService
        rtc=FakeRTC();clock=ClockService(rtc)
        clock.set_local((2025,1,1,0,30),'Europe/Madrid')
        self.assertEqual(rtc.stamp[:3],(2024,12,31))
        self.assertEqual(rtc.stamp[4:7],(23,30,0))
        self.assertEqual(ClockService(rtc).source,'retained')

    def test_manual_valid_without_wifi_and_ntp_transition(self):
        from clock_service import ClockService, AmbiguousTimeError
        rtc=FakeRTC();clock=ClockService(rtc)
        self.assertFalse(clock.ready)
        clock.set_local((2026,10,16,14,25),'Europe/Madrid')
        self.assertTrue(clock.ready);self.assertEqual(clock.source,'manual')
        snap=clock.snapshot()
        self.assertEqual(snap['utc'],'2026-10-16T12:25:00Z')
        self.assertEqual(snap['local'],'2026-10-16T14:25:00+02:00')
        with self.assertRaises(AmbiguousTimeError):
            clock.set_local((2026,10,25,2,30),'Europe/Madrid')
        clock.set_local((2026,10,25,2,30),'Europe/Madrid','winter')
        self.assertEqual(rtc.stamp[4],1)
        clock.set_local((2026,10,25,2,30),'Europe/Madrid','summer')
        self.assertEqual(rtc.stamp[4],0)
        clock.mark_ntp(1792888200)
        self.assertEqual(clock.source,'ntp')

    def test_rtc_metadata_validation(self):
        from clock_service import ClockService
        rtc=FakeRTC()
        for meta in (b'',b'corrupt',b'OTHER:manual',b'AURA08:invalid'):
            rtc.meta=meta;self.assertFalse(ClockService(rtc).ready)
        rtc.meta=b'AURA08:manual'
        self.assertFalse(ClockService(rtc).ready)
        rtc.stamp=(2026,10,16,4,12,0,0,0)
        self.assertEqual(ClockService(rtc).source,'retained')

    def test_rtc_failure_and_metadata_failure(self):
        from clock_service import ClockService
        rtc=FakeRTC();clock=ClockService(rtc);rtc.fail=True
        with self.assertRaises(OSError):clock.set_local((2026,1,1,12,0),'UTC')
        self.assertFalse(clock.ready)
        rtc.fail=False;rtc.fail_memory=True
        clock.set_local((2026,1,1,12,0),'UTC')
        self.assertTrue(clock.ready)
        self.assertFalse(clock.retention_available)

    def test_ntp_failure_preserves_manual_then_success(self):
        import test_connectivity
        from connectivity import Connectivity
        from clock_service import ClockService
        rtc=FakeRTC();clock=ClockService(rtc)
        clock.set_local((2026,1,15,12,0),'UTC')
        with patch('connectivity.wifi_config.SSID','test'), \
             patch('connectivity.time.ticks_ms',return_value=0,create=True), \
             patch('connectivity.time.ticks_diff',side_effect=lambda a,b:a-b,create=True), \
             patch('connectivity.time.ticks_add',side_effect=lambda a,b:a+b,create=True):
            link=Connectivity(clock)
            link.wlan.connected=True
            with patch('connectivity.ntp_client.sync',side_effect=OSError):link.poll()
            self.assertTrue(clock.ready);self.assertEqual(clock.source,'manual')
            link.next_ntp=0
            with patch('connectivity.ntp_client.sync',return_value=1768478400):link.poll()
            self.assertEqual(clock.source,'ntp')
