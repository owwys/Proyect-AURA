"""Configuracion del montaje ya comprobado; numeros GPIO, no pines fisicos."""
WIDTH = 320
HEIGHT = 240
SPI_ID = 1
SPI_HZ = 10_000_000
SCK = 12
MOSI = 11
CS = 10
DC = 13
RESET = 16
MADCTL = 0x28  # Horizontal
UPDATE_MS = 2000

# Version y hora local. RTC siempre en UTC; el desfase solo se aplica al mostrar.
FIRMWARE_VERSION = 'v0.8.1'
API_ENABLED = True
API_PORT = 8080
TIMEZONE = 'Europe/Madrid'  # Alternativas: Atlantic/Canary o UTC
WIFI_TIMEOUT_MS = 15000
WIFI_RETRY_MS = 30000
NTP_HOST = 'pool.ntp.org'
NTP_TIMEOUT_S = 3
NTP_RETRY_MS = 60000
NTP_INTERVAL_MS = 6 * 60 * 60 * 1000

# Tactil resistivo compatible XPT2046, SPI compartido.
TOUCH_ENABLED = True
TOUCH_CS = 17
TOUCH_MISO = 18
TOUCH_IRQ = 7
TOUCH_SPI_HZ = 1_000_000
TOUCH_CALIBRATION_FILE = 'touch_calibration.json'
TOUCH_POLL_MS = 20

# Alta inicial: automatica sin credenciales; True solo para prueba manual.
SETUP_ON_BOOT = False
