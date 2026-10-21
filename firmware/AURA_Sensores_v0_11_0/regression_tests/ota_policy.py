"""Contrato estable de instalacion. No se actualiza por OTA."""
PLATFORM = 'aura-esp32s3-landscape'
BOOTSTRAP = 1
MAX_FILE = 65536
MAX_TOTAL = 524288
MANAGED = (
    'clock_service.py', 'connectivity.py', 'demo.py', 'diagnostics.py',
    'font_aura.py', 'graphics.py', 'history.py', 'ili9341.py', 'local_api.py',
    'local_clock.py', 'main.py', 'menu.py', 'ntp_client.py', 'provisioning.py',
    'rendering.py', 'settings.py', 'setup_http.py', 'setup_mode.py',
    'tft_environment.py', 'tft_layout.py', 'touch.py', 'ui.py', 'web_page.py',
    'widgets.py', 'wifi_store.py', 'firmware_version.py', 'ota_client.py',
)


def version_tuple(value):
    if type(value) is not str or len(value) > 32:
        raise ValueError('Version no valida')
    parts = value[1:].split('.') if value.startswith('v') else value.split('.')
    if not 2 <= len(parts) <= 3 or any(not p or not p.isdigit() for p in parts):
        raise ValueError('Version no valida')
    numbers = tuple(int(p) for p in parts)
    if any(n > 9999 for n in numbers):
        raise ValueError('Version no valida')
    return numbers + (0,) * (3-len(numbers))
