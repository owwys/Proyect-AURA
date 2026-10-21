"""Instalador transaccional estable; se ejecuta antes de importar la aplicacion.

El diario se publica solo con respaldo completo. Restaurar copia, nunca consume,
el respaldo: puede repetirse tras otro reinicio. Requiere LittleFS y os.sync().
"""
import os
import json
import hashlib
import binascii
import sys
from ota_policy import MANAGED, PLATFORM, BOOTSTRAP, MAX_FILE, MAX_TOTAL, version_tuple

_started = None
_watchdog = None


def _path(root, name):
    return root.rstrip('/') + '/' + name


def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError as error:
        if error.args[0] == 2:
            return False
        raise


def _sync():
    os.sync()


def _remove(path):
    if _exists(path):
        os.remove(path)


def _mkdir(path):
    if not _exists(path):
        os.mkdir(path)


def digest(data):
    return binascii.hexlify(hashlib.sha256(data).digest()).decode()


def _file_digest(path):
    value = hashlib.sha256()
    with open(path, 'rb') as source:
        while True:
            chunk = source.read(1024)
            if not chunk:
                break
            value.update(chunk)
    return binascii.hexlify(value.digest()).decode()


def _copy(source, target):
    temporary = target + '.ota_tmp'
    with open(source, 'rb') as incoming, open(temporary, 'wb') as outgoing:
        while True:
            chunk = incoming.read(1024)
            if not chunk:
                break
            outgoing.write(chunk)
        outgoing.flush()
    _sync()
    os.rename(temporary, target)
    _sync()


def _write_state(root, state):
    path = _path(root, '.aura_ota/journal.json')
    with open(path+'.tmp', 'w') as output:
        json.dump(state, output)
        output.flush()
    _sync()
    os.rename(path+'.tmp', path)
    _sync()


def _read_state(root):
    path = _path(root, '.aura_ota/journal.json')
    if not _exists(path):
        return None
    if os.stat(path)[6] > 16384:
        raise ValueError('Diario OTA demasiado grande')
    with open(path) as source:
        state = json.load(source)
    if (state.get('phase') not in ('applying', 'ready', 'trial', 'confirmed') or
            type(state.get('old')) is not dict or set(state['old']) != set(MANAGED)):
        raise ValueError('Diario OTA no valido; requiere revision USB')
    for name, checksum in state['old'].items():
        if checksum is not None and (type(checksum) is not str or len(checksum) != 64 or
                any(c not in '0123456789abcdef' for c in checksum)):
            raise ValueError('Respaldo OTA no valido')
    return state


def validate_bundle(bundle):
    if (type(bundle) is not dict or bundle.get('schema') != 1 or
            bundle.get('platform') != PLATFORM or bundle.get('bootstrap') != BOOTSTRAP):
        raise ValueError('Paquete incompatible con este AURA')
    version_tuple(bundle.get('version'))
    files = bundle.get('files')
    if type(files) is not list or len(files) != len(MANAGED):
        raise ValueError('Paquete incompleto')
    seen = set()
    total = 0
    for entry in files:
        name = entry.get('name')
        if name not in MANAGED or name in seen:
            raise ValueError('Archivo no permitido')
        seen.add(name)
        size = entry.get('size')
        encoded = entry.get('hex')
        if (type(size) is not int or not 0 < size <= MAX_FILE or
                type(encoded) is not str or len(encoded) != size*2):
            raise ValueError('Tamano no valido')
        try:
            data = binascii.unhexlify(encoded)
        except (ValueError, TypeError):
            raise ValueError('Contenido no valido')
        if digest(data) != entry.get('sha256'):
            raise ValueError('SHA256 no coincide')
        try:
            compile(data.decode('utf-8'), name, 'exec')
        except (SyntaxError, UnicodeError):
            raise ValueError('Codigo Python no valido')
        total += size
    if total > MAX_TOTAL:
        raise ValueError('Paquete demasiado grande')
    version_file = next(e for e in files if e['name'] == 'firmware_version.py')
    if binascii.unhexlify(version_file['hex']).decode().strip() != "VERSION = %r" % bundle['version']:
        raise ValueError('Version del paquete incoherente')
    return total


def free_bytes(root):
    status = os.statvfs(root)
    return status[0] * status[4]


def check_filesystem():
    if sys.implementation.name == 'micropython':
        import vfs
        roots = [fs for fs, mountpoint in vfs.mount() if mountpoint == '/']
        if len(roots) != 1 or type(roots[0]).__name__ != 'VfsLfs2' or os.getcwd() != '/':
            raise ValueError('OTA requiere LittleFS2 en la raiz; revisar por USB')
    if not hasattr(os, 'sync'):
        raise ValueError('El firmware no admite sincronizacion de archivos')


def _cleanup(root):
    # Solo nombres propios; nunca recorrer ni borrar otros archivos de la placa.
    for folder in ('stage', 'backup'):
        for name in MANAGED:
            path = _path(root, '.aura_ota/'+folder+'/'+name)
            _remove(path)
            _remove(path+'.ota_tmp')
    for name in MANAGED:
        _remove(_path(root, name+'.ota_tmp'))
    _remove(_path(root, '.aura_ota/journal.json.tmp'))
    _sync()


def install(bundle, root='.'):
    """Preparar, verificar y sustituir. Debe seguir un reinicio, no un import."""
    check_filesystem()
    total = validate_bundle(bundle)
    if _read_state(root) is not None:
        raise ValueError('Hay una actualizacion pendiente de resolver')
    _mkdir(_path(root, '.aura_ota'))
    _mkdir(_path(root, '.aura_ota/stage'))
    _mkdir(_path(root, '.aura_ota/backup'))
    _cleanup(root)
    old = {}
    old_size = 0
    for name in MANAGED:
        path = _path(root, name)
        old[name] = _file_digest(path) if _exists(path) else None
        if old[name] is not None:
            old_size += os.stat(path)[6]
    # Reserva para temporales, diario y bloques del sistema de archivos.
    if free_bytes(root) < total + old_size + MAX_FILE + 131072:
        raise OSError('Espacio insuficiente para actualizar con respaldo')
    for entry in bundle['files']:
        path = _path(root, '.aura_ota/stage/'+entry['name'])
        with open(path, 'wb') as output:
            output.write(binascii.unhexlify(entry['hex']))
            output.flush()
        _sync()
        if _file_digest(path) != entry['sha256']:
            raise ValueError('Error al guardar la descarga')
    for name, checksum in old.items():
        if checksum is not None:
            path = _path(root, '.aura_ota/backup/'+name)
            _copy(_path(root, name), path)
            if _file_digest(path) != checksum:
                raise ValueError('Error al verificar respaldo')
    state = {'phase':'applying', 'version':bundle['version'], 'old':old}
    _write_state(root, state)
    # Cualquier fallo desde aqui obliga a reiniciar y restaurar, nunca continuar.
    for entry in bundle['files']:
        name = entry['name']
        _copy(_path(root, '.aura_ota/stage/'+name), _path(root, name))
    state['phase'] = 'ready'
    _write_state(root, state)
    return state['version']


def _restore(root, state):
    # Comprobar todos los respaldos ANTES de restaurar el primer modulo.
    for name, checksum in state['old'].items():
        if checksum is not None and _file_digest(_path(root, '.aura_ota/backup/'+name)) != checksum:
            raise ValueError('Respaldo danado; detener y recuperar por USB')
    for name, checksum in state['old'].items():
        target = _path(root, name)
        if checksum is None:
            _remove(target)
        else:
            _copy(_path(root, '.aura_ota/backup/'+name), target)
    _sync()
    _remove(_path(root, '.aura_ota/journal.json'))
    _sync()
    _cleanup(root)


def start(root='.', watchdog=False):
    global _started, _watchdog
    if _started is not None:
        return _started
    state = _read_state(root)
    if state is None:
        _started = 'clean'
    elif state['phase'] in ('applying', 'trial'):
        _restore(root, state)
        _started = 'restored'
        print('OTA: version anterior restaurada')
    elif state['phase'] == 'confirmed':
        _remove(_path(root, '.aura_ota/journal.json'))
        _sync()
        _cleanup(root)
        _started = 'clean'
    else:
        state['phase'] = 'trial'
        _write_state(root, state)
        if watchdog:
            from machine import WDT
            _watchdog = WDT(timeout=30000)
        _started = 'trial'
    return _started


def feed():
    if _watchdog is not None:
        _watchdog.feed()


def confirm(root='.'):
    state = _read_state(root)
    if state is None:
        return
    if state['phase'] != 'trial':
        raise ValueError('No hay arranque de prueba')
    state['phase'] = 'confirmed'
    _write_state(root, state)
    print('OTA: arranque de prueba confirmado')
    # Reiniciar para desactivar el WDT de prueba y limpiar el respaldo en boot.
    # CPython/tests no crean WDT ni reinician.
    if _watchdog is not None:
        import machine
        machine.reset()
