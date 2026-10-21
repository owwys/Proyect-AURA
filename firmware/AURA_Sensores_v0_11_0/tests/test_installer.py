import hashlib, importlib.util, json, os, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SCRIPT=Path(__file__).resolve().parents[1]/'instalar_thonny.py'

class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        spec=importlib.util.spec_from_file_location('installer',SCRIPT)
        self.inst=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.inst)
        self.inst.sys=SimpleNamespace(platform='esp32')
        self.inst.os=SimpleNamespace(stat=lambda p:os.stat(self.path(p)),
            mkdir=lambda p:os.mkdir(self.path(p)),remove=lambda p:os.remove(self.path(p)),
            rename=lambda a,b:os.replace(self.path(a),self.path(b)),sync=lambda:None)
        native_open=open
        p=patch.object(self.inst,'open',lambda p,*a,**k:native_open(self.path(p),*a,**k),create=True)
        p.start();self.addCleanup(p.stop)
        self.path('/_aura_sensors').mkdir()
        for name,content in {'main.py':'old main','config.py':'pins','touch_calibration.json':'private','bme280_float.py':'user driver'}.items():
            self.path('/'+name).write_text(content)
        files={'main.py':'new main','bme280_float.py':'new driver','scd41.py':'new scd'}
        for name,content in files.items():self.path('/_aura_sensors/'+name).write_text(content)
        self.path('/_aura_sensors/manifest.json').write_text(json.dumps({
            'base':{n:self.sha(self.path('/'+n)) for n in ('main.py','config.py')},
            'files':{n:self.sha(self.path('/_aura_sensors/'+n)) for n in files}}))
    def path(self,p):return self.root/str(p).lstrip('/')
    def sha(self,p):return hashlib.sha256(p.read_bytes()).hexdigest()
    def test_install_backup_and_private_preservation(self):
        self.inst.install()
        self.assertEqual(self.path('/main.py').read_text(),'new main')
        self.assertEqual(self.path('/aura_before_sensors_v0110/main.py').read_text(),'old main')
        self.assertEqual(self.path('/aura_before_sensors_v0110/bme280_float.py').read_text(),'user driver')
        self.assertEqual(self.path('/touch_calibration.json').read_text(),'private')
        self.assertEqual(self.path('/config.py').read_text(),'pins')
    def test_changed_base_stops_before_backup(self):
        self.path('/main.py').write_text('different')
        with self.assertRaises(RuntimeError):self.inst.install()
        self.assertFalse(self.path('/aura_before_sensors_v0110').exists())
    def test_corrupt_stage_stops_before_backup(self):
        self.path('/_aura_sensors/scd41.py').write_text('corrupt')
        with self.assertRaises(ValueError):self.inst.install()
        self.assertEqual(self.path('/main.py').read_text(),'old main')
    def test_pending_ota_stops(self):
        self.path('/.aura_ota').mkdir();self.path('/.aura_ota/journal.json').write_text('{}')
        with self.assertRaises(RuntimeError):self.inst.install()
        self.assertFalse(self.path('/aura_before_sensors_v0110').exists())
    def test_write_failure_restores_overwritten_driver(self):
        rename=self.inst.os.rename
        def fail_once(a,b):
            if a=='/main.py.sensors_tmp':raise OSError('injected')
            rename(a,b)
        self.inst.os.rename=fail_once
        with self.assertRaises(OSError):self.inst.install()
        self.assertEqual(self.path('/main.py').read_text(),'old main')
        self.assertEqual(self.path('/bme280_float.py').read_text(),'user driver')
        self.assertFalse(self.path('/scd41.py').exists())
