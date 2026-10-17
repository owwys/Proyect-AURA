# Diagnostico temporal de etapas; no cambia pines ni calibracion.
def _etapa(texto):
    import time
    with open('aura_etapas.log', 'a') as archivo:
        archivo.write('%d %s\n' % (time.ticks_ms(), texto))

"""AURA v0.7: dibujar solo al cambiar la imagen, priorizar el contacto tactil."""
import gc
import time
import config
from ili9341 import Display
from demo import DemoSource
from ui import Dashboard, clock_text
from touch import Touch
from menu import Navigation
from connectivity import Connectivity
from settings import Settings
from history import History
from rendering import FrameGate, render_key, calibration_status, touch_busy


def run(diagnostics=False):
    _etapa('RUN inicio')
    gc.collect()
    display = None
    stats = None
    elapsed_ms = 0
    try:
        if diagnostics:
            from diagnostics import Diagnostics
            stats = Diagnostics()
        settings = Settings()
        settings.apply()
        history = History()
        _etapa('Display antes')
        display = Display()
        _etapa('Display despues')
        dashboard = Dashboard(display)
        _etapa('Dashboard creado')
        touch = Touch(display) if config.TOUCH_ENABLED else None
        _etapa('Touch creado')
        navigation = Navigation(touch, settings)
        source = DemoSource()
        data = source.read()
        history.add(0, data)
        revision = 1
        _etapa('Connectivity antes')
        link = Connectivity()
        _etapa('Connectivity despues')
        gate = FrameGate()
        previous = time.ticks_ms()
        last_demo = previous
        last_clock = previous
        last_report = previous
        hour = '--:--'
        clock_state = None
        _etapa('Anuncio consola antes')
        print('AURA', config.FIRMWARE_VERSION, '/ Ctrl+C para detener')
        print('Tactil:', calibration_status(touch))
        _etapa('Anuncio consola despues')
        while True:
            now = time.ticks_ms()
            elapsed_ms += time.ticks_diff(now, previous)
            previous = now
            if stats:
                stats.poll(now)
            event_time = None
            changed = False
            if touch is not None:
                raw = touch.poll()
                if raw is not None:
                    event_time = time.ticks_ms() if stats else None
                    changed = navigation.handle(raw)
            busy = touch_busy(touch)
            if time.ticks_diff(now, last_demo) >= config.UPDATE_MS:
                data = source.read()
                history.add(elapsed_ms//1000, data)
                revision += 1
                last_demo = now
            # Leer el reloj una vez por segundo; tambien al sincronizar/cambiar zona.
            new_clock_state = (link.synced, config.TIMEZONE)
            if new_clock_state != clock_state or time.ticks_diff(now, last_clock) >= 1000:
                hour = clock_text() if link.synced else '--:--'
                last_clock = now
                clock_state = new_clock_state
            key = render_key(navigation, data, revision, link, hour)
            if stats and changed and key != gate.previous:
                stats.event(event_time)
            if gate.ready(key, busy):
                if gate.previous is None:
                    _etapa('Primer dibujo antes: ' + navigation.page)
                started = time.ticks_us() if stats else None
                state = calibration_status(touch)
                if navigation.page == 'calibrate':
                    dashboard.draw_calibration(len(navigation.samples),
                                               navigation.candidate is not None,
                                               navigation.error)
                elif navigation.page == 'trends':
                    dashboard.draw_trends(history, navigation.metric)
                elif navigation.page == 'settings':
                    dashboard.draw_settings(navigation.interval, navigation.zone,
                                            navigation.message, state)
                elif navigation.page == 'home':
                    dashboard.draw(data, elapsed_ms//1000, link.caption(), link.synced, state)
                else:
                    dashboard.draw_menu(navigation.page, link, state)
                if gate.previous is None:
                    _etapa('Primer dibujo despues')
                gate.commit(key)
                if stats:
                    stats.frame(time.ticks_ms(), time.ticks_diff(time.ticks_us(), started))
            # No iniciar DNS/NTP durante contacto ni durante el antirrebote al soltar.
            # Una consulta ya iniciada sigue siendo sincrona y no se puede interrumpir.
            if not touch_busy(touch):
                network_start = time.ticks_ms() if stats else None
                link.poll()
                if stats:
                    stats.max_network_ms = max(stats.max_network_ms,
                                                time.ticks_diff(time.ticks_ms(), network_start))
            if stats and not touch_busy(touch) and time.ticks_diff(now, last_report) >= 30000:
                stats.report(elapsed_ms//1000)
                last_report = time.ticks_ms()
            time.sleep_ms(config.TOUCH_POLL_MS)
    except KeyboardInterrupt as error:
        _etapa('Interrupcion recibida')
        import sys
        with open('arranque.log', 'a') as f:
            f.write('INTERRUPCION RECIBIDA\n')
            sys.print_exception(error, f)
        print('AURA detenida.')
    finally:
        if display is not None:
            _etapa('SPI cierre antes')
            display.close()
            _etapa('SPI cierre despues')
        if stats is not None:
            stats.report(elapsed_ms//1000)


if __name__ == '__main__':
    run()
