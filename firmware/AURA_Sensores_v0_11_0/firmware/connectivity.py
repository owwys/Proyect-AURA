"""Conexion con reintentos: la demo continua aunque no haya red."""
import time
import network
import config
try:
    import wifi_config
except ImportError:
    wifi_config = None
import ntp_client


class Connectivity:
    def __init__(self, clock=None):
        self.clock = clock
        interface = getattr(network, 'STA_IF', None)
        if interface is None:
            interface = network.WLAN.IF_STA
        # Debe fijarse antes de conectar: DHCP y mDNS usan este nombre.
        try:network.hostname('aura')
        except (AttributeError,OSError,ValueError):
            print('Nombre local no disponible; usar direccion IP.')
        self.wlan = network.WLAN(interface)
        self.ntp_ok = False
        self.synced = False  # Solo confirma una consulta NTP exitosa de esta ejecucion.
        self.connecting_since = None
        self.next_wifi = time.ticks_ms()
        self.next_ntp = self.next_wifi
        from wifi_store import WiFiStore
        store = WiFiStore()
        saved = store.load()
        self.ssid, self.password = saved if saved else (getattr(wifi_config, 'SSID', ''), getattr(wifi_config, 'PASSWORD', ''))
        self.enabled = bool(self.ssid)
        self.setup_needed = not self.enabled
        if self.enabled:
            self.wlan.active(True)
            # El gestor decide cuando reintentar, sin reconexiones ilimitadas.
            try:
                self.wlan.config(reconnects=0)
            except (ValueError, OSError):
                pass  # Opcion no disponible en algunos builds.
        else:
            print('Wi-Fi sin configurar: edita wifi_config.py')

    def offline(self):
        self.enabled=False;self.setup_needed=False;self.ssid='';self.password=''
        self.ntp_ok=False;self.synced=False;self.connecting_since=None
        try:self.wlan.disconnect()
        except OSError:pass
        try:self.wlan.active(False)
        except OSError:pass

    def forget(self):
        from wifi_store import WiFiStore
        WiFiStore().clear()
        if wifi_config is not None:
            wifi_config.SSID='';wifi_config.PASSWORD=''
        self.offline()
        self.setup_needed=True

    def caption(self):
        if not self.enabled:
            return 'SIN WIFI'
        if self.wlan.isconnected():
            if self.ntp_ok:
                return 'WIFI OK / NTP OK'
            return 'WIFI OK / RTC OK' if self.synced else 'WIFI OK / SIN HORA'
        if self.connecting_since is not None:
            return 'WIFI...'
        return 'WIFI OFF / RTC OK' if self.synced else 'WIFI OFF'

    def poll(self):
        if not self.enabled:
            return
        now = time.ticks_ms()
        if not self.wlan.isconnected():
            if self.connecting_since is not None:
                status = self.wlan.status()
                if status < 0 or time.ticks_diff(now, self.connecting_since) >= config.WIFI_TIMEOUT_MS:
                    self.wlan.disconnect()
                    self.connecting_since = None
                    self.next_wifi = time.ticks_add(now, config.WIFI_RETRY_MS)
                    print('Wi-Fi no conectado; nuevo intento en 30 s. Estado:', status)
                return
            if time.ticks_diff(now, self.next_wifi) >= 0:
                try:
                    self.wlan.connect(self.ssid, self.password)
                    self.connecting_since = now
                    print('Conectando Wi-Fi...')
                except OSError:
                    self.next_wifi = time.ticks_add(now, config.WIFI_RETRY_MS)
                    print('No se pudo iniciar Wi-Fi; se reintentara.')
            return
        if self.connecting_since is not None:
            self.connecting_since = None
            print('Wi-Fi conectado. IP:', self.wlan.ifconfig()[0])
        if time.ticks_diff(now, self.next_ntp) < 0:
            return
        try:
            seconds = ntp_client.sync(config.NTP_HOST, config.NTP_TIMEOUT_S)
            if self.clock is not None:
                self.clock.mark_ntp(seconds)
            self.synced = True
            self.ntp_ok = True
            delay = config.NTP_INTERVAL_MS
            print('Hora sincronizada por NTP (RTC en UTC).')
        except OSError:
            self.ntp_ok = False
            delay = config.NTP_RETRY_MS
            print('NTP no disponible; nuevo intento en 60 s.')
        self.next_ntp = time.ticks_add(time.ticks_ms(), delay)
