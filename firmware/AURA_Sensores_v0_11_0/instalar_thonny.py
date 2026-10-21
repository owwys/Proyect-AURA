"""Execute this LOCAL file in Thonny after copying _aura_sensors to the ESP32.

Do not save as main.py. A changed baseline stops installation before writes.
No reboot is performed automatically. Physical power loss is not covered.
"""
import os
import sys
import json
import hashlib
import binascii

STAGE = '/_aura_sensors'
BACKUP = '/aura_before_sensors_v0110'


def exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        while True:
            part = stream.read(1024)
            if not part:
                break
            h.update(part)
    return binascii.hexlify(h.digest()).decode()


def copy(source, target):
    with open(source, 'rb') as src, open(target, 'wb') as dst:
        while True:
            part = src.read(1024)
            if not part:
                break
            dst.write(part)
    os.sync()
    if digest(source) != digest(target):
        raise OSError('Copy verification failed: '+target)


def install():
    if sys.platform != 'esp32':
        raise RuntimeError('Run using the ESP32 MicroPython interpreter')
    if not hasattr(os, 'sync'):
        raise RuntimeError('os.sync required')
    if exists('/.aura_ota/journal.json'):
        raise RuntimeError('OTA transaction pending: let normal boot finish first')
    if exists(BACKUP):
        raise RuntimeError('Backup already exists; do not overwrite it')
    with open(STAGE+'/manifest.json') as stream:
        manifest = json.load(stream)
    # Verify ALL known v0.10.1 modules, including the protected config reference.
    for name, expected in manifest['base'].items():
        if not exists('/'+name) or digest('/'+name) != expected:
            raise RuntimeError('Base differs from v0.10.1: '+name)
        for folder in ('/', '/lib/'):
            if exists(folder+name[:-3]+'.mpy'):
                raise RuntimeError('Compiled baseline module: '+name)
    for name, expected in manifest['files'].items():
        if '/' in name or not name.endswith('.py'):
            raise ValueError('Invalid module name')
        if digest(STAGE+'/'+name) != expected:
            raise ValueError('Staging file differs: '+name)
        for folder in ('/', '/lib/'):
            if exists(folder+name[:-3]+'.mpy'):
                raise RuntimeError('Compiled module could shadow source: '+name)
    protected = {}
    for name in ('config.py', 'touch.py', 'ili9341.py', 'tft_layout.py',
                 'touch_calibration.json', 'wifi_config.py', 'wifi_settings.json',
                 'aura_settings.json', 'boot.py', 'ota_boot.py', 'ota_policy.py'):
        if exists('/'+name):
            protected[name] = digest('/'+name)
    os.mkdir(BACKUP)
    originals = {}
    for name in manifest['files']:
        originals[name] = digest('/'+name) if exists('/'+name) else None
        if originals[name] is not None:
            copy('/'+name, BACKUP+'/'+name)
    with open(BACKUP+'/originals.json', 'w') as stream:
        json.dump(originals, stream)
    os.sync()
    # Import dependencies first; main is the last program file activated.
    order = sorted(n for n in manifest['files'] if n != 'main.py') + ['main.py']
    changed = []
    try:
        for name in order:
            copy(STAGE+'/'+name, '/'+name+'.sensors_tmp')
            changed.append(name)
            os.rename('/'+name+'.sensors_tmp', '/'+name)
            os.sync()
            if digest('/'+name) != manifest['files'][name]:
                raise OSError('Installed hash differs: '+name)
        for name, expected in protected.items():
            if digest('/'+name) != expected:
                raise OSError('Protected file differs: '+name)
    except Exception:
        for name in reversed(changed):
            if originals[name] is None:
                if exists('/'+name): os.remove('/'+name)
            else:
                copy(BACKUP+'/'+name, '/'+name+'.restore_tmp')
                os.rename('/'+name+'.restore_tmp', '/'+name)
                os.sync()
        print('Installation cancelled; original program restored. Backup:', BACKUP)
        raise
    print('v0.11.0 files installed and verified. Configuration unchanged.')
    print('Backup:', BACKUP)
    print('Press RESET/EN. Hardware acceptance tests are still pending.')


if __name__ == '__main__':
    install()
