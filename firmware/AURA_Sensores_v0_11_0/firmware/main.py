"""AURA horizontal con actualizacion OTA y configuracion privada preservada."""
import ota_boot
OTA_BOOT_STATE = ota_boot.start(watchdog=True)
import gc
import time
import config
from firmware_version import VERSION
config.FIRMWARE_VERSION = VERSION  # Solo RAM; config.py y sus pines no se sobrescriben.
from ili9341 import Display
from sensor_source import SensorSource
from ui import Dashboard, clock_text
from touch import Touch
from menu import Navigation
from connectivity import Connectivity
from settings import Settings
from history import History
from clock_service import ClockService
from local_api import LocalAPI, make_snapshot
from rendering import FrameGate, render_key, calibration_status, touch_busy


def run(diagnostics=False):
    gc.collect()
    display = None
    stats = None
    api = None
    setup = None
    elapsed_ms = 0
    try:
        if diagnostics:
            from diagnostics import Diagnostics
            stats = Diagnostics()
        clock = ClockService()
        settings = Settings()
        settings.apply()
        history = History()
        display = Display()
        dashboard = Dashboard(display)
        touch = Touch(display) if config.TOUCH_ENABLED else None
        navigation = Navigation(touch, settings, clock)
        source = SensorSource()
        data = source.snapshot(time.ticks_ms())
        history.add(0, data)
        captured_uptime_ms = 0
        captured_utc = clock.snapshot()['utc']
        revision = 1
        link = Connectivity(clock)
        setup_pending = getattr(link, 'setup_needed', False)
        if setup_pending and navigation.page != 'calibrate':
            from setup_mode import SetupMode
            setup = SetupMode(link.wlan, time.ticks_ms())
            setup_pending = False
        def connected():
            return bool(link.enabled and link.wlan.isconnected())
        def public_snapshot():
            return make_snapshot(source.snapshot(time.ticks_ms()), captured_uptime_ms, captured_utc, elapsed_ms,
                                 clock.snapshot(), connected())
        api = LocalAPI(public_snapshot, enabled=config.API_ENABLED, port=config.API_PORT)
        gate = FrameGate()
        previous = time.ticks_ms()
        last_sample = previous
        last_clock = previous
        last_report = previous
        hour = '--:--'
        clock_state = None
        ota_candidate = None
        trial_started = previous
        trial_frames = 0
        trial_confirmed = OTA_BOOT_STATE != 'trial'
        print('AURA', config.FIRMWARE_VERSION, '/ Ctrl+C para detener')
        print('Tactil:', calibration_status(touch))
        while True:
            ota_boot.feed()
            now = time.ticks_ms()
            elapsed_ms += time.ticks_diff(now, previous)
            previous = now
            if stats:
                stats.poll(now)
            event_time = None
            changed = False
            if touch is not None:
                raw = touch.poll()
                if raw is not None and setup is not None:
                    from menu import contains
                    from tft_layout import SETUP_SKIP
                    point = navigation.touch.screen_point(raw)
                    if point is not None and setup.snapshot()['state'] != 'connected' and contains(SETUP_SKIP,point):
                        if setup.skip():
                            link.offline();setup=None;setup_pending=False
                            navigation.page='home';gate.previous=None
                elif raw is not None:
                    event_time = time.ticks_ms() if stats else None
                    changed = navigation.handle(raw)
            busy = touch_busy(touch)
            if setup is None and not busy and navigation.ota_action:
                action = navigation.ota_action
                navigation.ota_action = None
                if not trial_confirmed:
                    navigation.ota_state = 'trial'
                    navigation.ota_message = 'Espera a completar el arranque'
                elif not connected():
                    navigation.ota_state = 'error'
                    navigation.ota_message = 'Conecta AURA a tu Wi-Fi primero'
                elif not clock.ready:
                    navigation.ota_state = 'error'
                    navigation.ota_message = 'Ajusta fecha y hora en el menu'
                else:
                    navigation.ota_state = 'checking' if action == 'check' else 'installing'
                    dashboard.draw_updates(navigation.ota_state, navigation.ota_version)
                    try:
                        import ota_client
                        if action == 'check':
                            ota_candidate = ota_client.check()
                            navigation.ota_state = 'available' if ota_candidate else 'current'
                            navigation.ota_version = ota_candidate['version'] if ota_candidate else ''
                            navigation.ota_message = ''
                        elif action == 'install' and ota_candidate is not None:
                            api.close()
                            ota_client.apply(ota_candidate)
                    except Exception as error:
                        navigation.ota_state = 'error'
                        navigation.ota_message = 'Revisa red, hora y publicacion'
                        # Nunca imprimir URLs firmadas ni credenciales.
                        print('OTA: no se completo la operacion:', type(error).__name__)
                    gc.collect()
                gate.previous = None
            if setup is None and not busy:
                if getattr(navigation,'wifi_action',None) == 'reset':
                    navigation.wifi_action=None
                    try:link.forget()
                    except OSError:navigation.message='No se pudo borrar. Reintenta.'
                    else:
                        api.close();setup_pending=True;navigation.page='home'
                if setup_pending and navigation.page != 'calibrate':
                    from setup_mode import SetupMode
                    setup=SetupMode(link.wlan,time.ticks_ms())
                    setup_pending=False;gate.previous=None
            if setup is not None and not busy:
                setup.poll(time.ticks_ms())
                if setup.session and setup.session.state == 'connected':
                    link.enabled = True
                    if not setup.session.active:
                        from wifi_store import WiFiStore
                        link.ssid, link.password = WiFiStore().load()
                        setup = None
                        gate.previous = None
            if not busy:
                source.poll(now)
            data = source.snapshot(now)
            if time.ticks_diff(now, last_sample) >= config.UPDATE_MS:
                captured_uptime_ms = elapsed_ms
                captured_utc = clock.snapshot()['utc']
                history.add(elapsed_ms//1000, data)
                revision += 1
                last_sample = now
            # Leer el reloj una vez por segundo; tambien al sincronizar/cambiar zona.
            new_clock_state = (clock.ready, clock.source, config.TIMEZONE)
            if new_clock_state != clock_state or time.ticks_diff(now, last_clock) >= 1000:
                local = clock.snapshot()['local']
                hour = local[11:16] if local else '--:--'
                last_clock = now
                clock_state = new_clock_state
            ip = link.wlan.ifconfig()[0] if connected() else None
            if ip == '0.0.0.0':
                ip = None
            api.poll(time.ticks_ms(), ip, busy=touch_busy(touch))
            api_state = api.status()
            key = render_key(navigation, data, revision, link, hour, clock, api_state)
            if setup is not None:
                status = setup.snapshot()
                key = ('setup', status['state'], status.get('ip'), status.get('error'),status.get('notice'))
            elif navigation.page == 'wifi_confirm':
                key = ('wifi_confirm',navigation.message)
            elif navigation.page == 'updates':
                key = ('updates', navigation.ota_state, navigation.ota_version, navigation.ota_message)
            if stats and changed and key != gate.previous:
                stats.event(event_time)
            if gate.ready(key, busy):
                started = time.ticks_us() if stats else None
                state = calibration_status(touch)
                if setup is not None:
                    dashboard.draw_setup(setup.snapshot(), setup.key, setup.wifi_key)
                elif navigation.page == 'wifi_confirm':
                    dashboard.draw_wifi_confirm(navigation.message)
                elif navigation.page == 'updates':
                    dashboard.draw_updates(navigation.ota_state, navigation.ota_version, navigation.ota_message)
                elif navigation.page == 'calibrate':
                    dashboard.draw_calibration(len(navigation.samples),
                                               navigation.candidate is not None,
                                               navigation.error)
                elif navigation.page == 'trends':
                    dashboard.draw_trends(history, navigation.metric)
                elif navigation.page == 'clock':
                    dashboard.draw_clock(navigation.clock_editor, config.TIMEZONE, clock.source)
                elif navigation.page == 'settings':
                    dashboard.draw_settings(navigation.interval, navigation.zone,
                                            navigation.message, state)
                elif navigation.page == 'home':
                    dashboard.draw(data, elapsed_ms//1000, link.caption(), clock.ready, state, clock)
                else:
                    dashboard.draw_menu(navigation.page, link, state, clock, api_state)
                gate.commit(key)
                trial_frames += 1
                if stats:
                    stats.frame(time.ticks_ms(), time.ticks_diff(time.ticks_us(), started))
            # No iniciar DNS/NTP durante contacto ni durante el antirrebote al soltar.
            # Una consulta ya iniciada sigue siendo sincrona y no se puede interrumpir.
            if setup is None and not touch_busy(touch):
                network_start = time.ticks_ms() if stats else None
                link.poll()
                if stats:
                    stats.max_network_ms = max(stats.max_network_ms,
                                                time.ticks_diff(time.ticks_ms(), network_start))
            if stats and not touch_busy(touch) and time.ticks_diff(now, last_report) >= 30000:
                stats.report(elapsed_ms//1000)
                last_report = time.ticks_ms()
            if not trial_confirmed and trial_frames and time.ticks_diff(time.ticks_ms(),trial_started) >= 20000:
                # La salud no depende de Internet, NTP ni de disponer de sensores.
                ota_boot.confirm()
                trial_confirmed = True
            time.sleep_ms(config.TOUCH_POLL_MS)
    except KeyboardInterrupt:
        print('AURA detenida.')
    finally:
        if setup is not None:
            setup.close()
        if api is not None:
            api.close()
        if display is not None:
            display.close()
        if stats is not None:
            stats.report(elapsed_ms//1000)


if __name__ == '__main__':
    run()
