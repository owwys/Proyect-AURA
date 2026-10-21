"""Buscar una release una sola vez y fijar su paquete hasta instalarlo."""
import gc
import json
import ota_boot
from ota_policy import version_tuple
from firmware_version import VERSION

ASSET = 'aura-firmware.json'
MAX_BUNDLE = 1100000


def select_release(release, current, repository):
    if type(release) is not dict or release.get('draft') is not False or release.get('prerelease') is not False:
        raise ValueError('No es una version estable')
    version = release.get('tag_name')
    if version_tuple(version) <= version_tuple(current):
        return None
    matches = [a for a in release.get('assets', []) if a.get('name') == ASSET]
    if len(matches) != 1:
        raise ValueError('La release no contiene paquete AURA')
    asset = matches[0]
    size = asset.get('size')
    url = asset.get('browser_download_url')
    expected = 'https://github.com/'+repository+'/releases/download/'+version+'/'+ASSET
    if (asset.get('state') != 'uploaded' or type(size) is not int or
            not 0 < size <= MAX_BUNDLE or url != expected):
        raise ValueError('Paquete de release no valido')
    checksum = asset.get('digest', '')
    if (type(checksum) is not str or not checksum.startswith('sha256:') or
            len(checksum) != 71 or any(c not in '0123456789abcdef' for c in checksum[7:])):
        raise ValueError('GitHub no proporciona SHA256 del paquete')
    return {'version':version, 'url':url, 'size':size, 'sha256':checksum[7:]}


def check():
    from ota_https import get
    from ota_source import REPOSITORY
    parts = REPOSITORY.split('/')
    if len(parts) != 2 or any(not p or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._' for c in p) for p in parts):
        raise ValueError('Repositorio OTA no valido')
    gc.collect()
    raw = get('https://api.github.com/repos/'+REPOSITORY+'/releases/latest')
    return select_release(json.loads(raw), VERSION, REPOSITORY)


def apply(candidate):
    from ota_https import get
    import machine
    gc.collect()
    raw = get(candidate['url'], MAX_BUNDLE)
    if len(raw) != candidate['size'] or ota_boot.digest(raw) != candidate['sha256']:
        raise ValueError('Paquete descargado incompleto o modificado')
    package = json.loads(raw)
    del raw
    gc.collect()
    if package.get('version') != candidate['version']:
        raise ValueError('Version descargada distinta a la elegida')
    try:
        ota_boot.install(package)
    except Exception:
        # Reiniciar incluso si tampoco puede leerse el diario. El boot resolvera
        # la transaccion antes de importar cualquier modulo de la aplicacion.
        machine.reset()
        raise
    machine.reset()
