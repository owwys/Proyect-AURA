import sys, time, unittest, types, struct
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'firmware'))
sys.modules['ustruct'] = struct
sys.modules['micropython'] = types.SimpleNamespace(const=lambda v:v)
time.ticks_add = lambda a,b: (a+b) % (1<<30)
time.ticks_diff = lambda a,b: ((a-b+(1<<29)) % (1<<30))-(1<<29)
from sensor_source import SensorSource
from bme280_periodic import PeriodicBME280

class SourceTests(unittest.TestCase):
    def source(self): return SensorSource(bus_factory=lambda: object())
    def good(self, source, name, at, **sample):
        source.slots[name].update(sample=sample, at=at, error=None)

    def test_no_sensors_no_demo(self):
        data=self.source().snapshot(0)
        self.assertFalse(data['demo'])
        self.assertTrue(all(data[k] is None for k in ('co2','temperature','humidity','pressure')))

    def test_priority_fallback_and_staleness(self):
        source=self.source()
        self.good(source,'bme280',1000,temperature=22.6,humidity=44,pressure=941.4)
        self.good(source,'scd41',1000,co2=1369,temperature=24.5,humidity=48.62)
        self.assertEqual(source.snapshot(1001)['temperature'],22.6)
        source.slots['bme280']['error']='ENODEV'
        data=source.snapshot(1002)
        self.assertEqual(data['temperature'],24.5)
        self.assertEqual(data['sources']['temperature'],'scd41')
        self.assertIsNone(data['pressure'])
        self.assertIsNone(source.snapshot(16001)['co2'])

    def test_age_independent_and_ticks_wrap(self):
        source=self.source(); wrap=(1<<30)
        self.good(source,'scd41',wrap-1000,co2=1369,temperature=24.5,humidity=48.62)
        self.good(source,'bme280',500,temperature=22.6,humidity=44,pressure=941.4)
        data=source.snapshot(1000)
        self.assertEqual(data['field_age_ms']['co2'],2000)
        self.assertEqual(data['field_age_ms']['temperature'],500)
        self.assertIsNone(source.snapshot(15001)['co2'])

    def test_error_retries_and_recovers_independently(self):
        source=self.source(); source.poll(0)
        class Failing:
            def __init__(self,bus): pass
            def poll(self,now): raise OSError(19)
        class Working:
            def __init__(self,bus): pass
            def poll(self,now): return dict(temperature=22.6,humidity=44,pressure=941.4)
        source.factories.update(scd41=Failing,bme280=Working)
        source.poll(10); source.poll(20)
        self.assertEqual(source.snapshot(20)['pressure'],941.4)
        self.assertIsNone(source.snapshot(20)['co2'])
        class Recovered:
            def __init__(self,bus): pass
            def poll(self,now): return dict(co2=1369,temperature=24.5,humidity=48.62)
        source.factories['scd41']=Recovered
        source.poll(10000); self.assertIsNone(source.snapshot(10000)['co2'])
        source.poll(10011);source.poll(10012)
        self.assertEqual(source.snapshot(10012)['co2'],1369)

    def test_bus_failure_retried(self):
        calls=[]
        def factory(): calls.append(1); raise OSError(19)
        source=SensorSource(factory)
        source.poll(0);source.poll(9999);self.assertEqual(len(calls),1)
        source.poll(10000);self.assertEqual(len(calls),2)

    def test_retry_gets_full_warmup_after_old_sample(self):
        source=self.source();source.poll(0)
        self.good(source,'scd41',0,co2=1369,temperature=24.5,humidity=48.62)
        class Warming:
            def __init__(self,bus):pass
            def poll(self,now):return None
        source.factories['scd41']=Warming
        source.factories['bme280']=Warming
        source.poll(30000)
        self.assertIsNone(source.slots['scd41']['error'])
        source.poll(30001);source.poll(40000)
        self.assertIsNone(source.slots['scd41']['error'])
        source.poll(40001);source.poll(50001)
        self.assertIn('timeout',source.slots['scd41']['error'])

class BMEBus:
    def __init__(self): self.writes=[]; self.busy=False
    def readfrom_mem(self,address,reg,count):
        if reg==0xd0:return b'\x60'
        if reg==0xf3:return bytes([8 if self.busy else 0])
        if reg==0x88:return struct.pack('<HhhHhhhhhhhhBB',27504,26435,-1000,36477,-10685,3024,2855,140,-7,15500,-14600,6000,0,75)
        if reg==0xe1:return bytes.fromhex('6a01001425031e')
        raise AssertionError(reg)
    def writeto_mem(self,address,reg,value):self.writes.append((reg,bytes(value)))
    def readfrom_mem_into(self,address,reg,target):
        def adc(v):return bytes((v>>12,(v>>4)&255,(v&15)<<4))
        target[:]=adc(415148)+adc(519888)+b'\x75\x30'

class BMETests(unittest.TestCase):
    def test_bosch_vector_and_pressure_units(self):
        bus=BMEBus();driver=PeriodicBME280(bus)
        for now in (0,10,11,12,13,33): self.assertIsNone(driver.poll(now))
        data=driver.poll(34)
        self.assertAlmostEqual(data['temperature'],25.08,places=2)
        self.assertAlmostEqual(data['pressure'],1006.5327,places=3)
        self.assertEqual(bus.writes[-1],(0xf4,b'\x25'))
    def test_busy_conversion_timeout(self):
        bus=BMEBus();driver=PeriodicBME280(bus)
        for now in (0,10,11,12,13):driver.poll(now)
        bus.busy=True
        self.assertIsNone(driver.poll(33))
        with self.assertRaises(ValueError): driver.poll(213)

if __name__ == '__main__':unittest.main()
