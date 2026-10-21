"""Decidir cuando cambia la imagen; sin acceder al hardware de dibujo."""
CALIBRATION_LABELS = {
    'loaded': 'TACTIL: CARGADA',
    'saved': 'TACTIL: GUARDADA',
    'pending': 'TACTIL: PENDIENTE',
    'unsaved': 'TACTIL: SOLO EN RAM',
    'disabled': 'TACTIL: DESACTIVADO',
}


def calibration_status(touch):
    if touch is None:
        return 'disabled'
    return getattr(touch, 'calibration_state',
                   'loaded' if touch.matrix is not None else 'pending')


def touch_busy(touch):
    if touch is None:
        return False
    tracker = getattr(touch, 'tracker', None)
    return touch.irq.value() == 0 or (tracker is not None and tracker.started is not None)


def home_caption(link):
    status = 'SIN WIFI' if link is None else link.caption()
    if status.startswith('WIFI OK'):
        return 'WIFI OK'
    if status.startswith('WIFI OFF'):
        return 'WIFI OFF'
    return status


def render_key(nav, data, revision, link, hour, clock=None, api_state=None):
    page = nav.page
    state = calibration_status(nav.touch)
    if page == 'home':
        from tft_environment import assess, valid
        def shown(key, pattern, low, high):
            value = data.get(key)
            return pattern % value if valid(value, low, high) else '--'
        return (page, shown('co2', '%d', 0, 99999),
                shown('temperature', '%.1f', -40, 85),
                shown('humidity', '%d', 0, 100), shown('pressure', '%d', 300, 1200),
                assess(data), hour, home_caption(link), state, data.get('sensor_caption'))
    if page == 'trends':
        return page, nav.metric, revision
    if page == 'clock':
        editor = nav.clock_editor
        return (page, tuple(editor.parts), editor.field, editor.fold, editor.message,
                editor.ambiguous, clock.source if clock is not None else 'unset', editor.zone)
    if page == 'settings':
        return page, nav.interval, nav.zone, nav.message, state
    if page == 'calibrate':
        return page, len(nav.samples), nav.candidate is not None, nav.error
    if page == 'network':
        connected = link.enabled and link.wlan.isconnected()
        ip = link.wlan.ifconfig()[0] if connected else ''
        import config
        api_key = (api_state.get('state'), api_state.get('url')) if api_state else None
        return page, connected, ip, link.synced, config.TIMEZONE, clock.source if clock else None, api_key
    return page, state


class FrameGate:
    def __init__(self):
        self.previous = None

    def ready(self, key, busy):
        # Pintar siempre el arranque; luego esperar a finalizar el contacto.
        return self.previous is None or (key != self.previous and not busy)

    def commit(self, key):
        self.previous = key
