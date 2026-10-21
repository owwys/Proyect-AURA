"""ILI9341 vertical: framebuffer con colores preparados para envio directo SPI."""
import sys
import time
import framebuf
from machine import Pin, SPI
import config


def rgb565(r, g, b):
    """Color para ESTE framebuffer. No intercambiar otra vez al transmitir."""
    value = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    # ILI9341 recibe primero el byte alto; framebuf almacena enteros nativos.
    if sys.byteorder == 'little':
        return ((value & 255) << 8) | (value >> 8)
    return value


class Display:
    def __init__(self):
        self.width = config.WIDTH
        self.height = config.HEIGHT
        # Ambos dispositivos deben estar deseleccionados antes de iniciar el bus.
        self.cs = Pin(config.CS, Pin.OUT, value=1)
        self.touch_cs = Pin(config.TOUCH_CS, Pin.OUT, value=1)
        self.spi = SPI(config.SPI_ID, baudrate=config.SPI_HZ,
                       polarity=0, phase=0, sck=Pin(config.SCK),
                       mosi=Pin(config.MOSI), miso=Pin(config.TOUCH_MISO))
        self.cs = Pin(config.CS, Pin.OUT, value=1)
        self.dc = Pin(config.DC, Pin.OUT, value=0)
        self.reset = Pin(config.RESET, Pin.OUT, value=1)
        self.buffer = bytearray(self.width * self.height * 2)
        self.fb = framebuf.FrameBuffer(self.buffer, self.width, self.height,
                                      framebuf.RGB565)
        self._view = memoryview(self.buffer)
        self.init()

    def command(self, value, data=None):
        self.cs.value(0)
        try:
            self.dc.value(0)
            self.spi.write(bytes([value]))
            if data is not None:
                self.dc.value(1)
                self.spi.write(bytes(data))
        finally:
            self.cs.value(1)

    def init(self):
        self.reset.value(0)
        time.sleep_ms(100)
        self.reset.value(1)
        time.sleep_ms(150)
        self.command(0x01)  # Software reset
        time.sleep_ms(150)
        self.command(0x28)  # Display off mientras se configura
        self.command(0x3A, [0x55])  # 16 bits/pixel
        self.command(0x36, [config.MADCTL])
        self.command(0x11)  # Sleep out
        time.sleep_ms(150)
        self.fb.fill(0)
        self.show()
        self.command(0x29)
        time.sleep_ms(100)

    def show(self):
        x = self.width - 1
        y = self.height - 1
        self.command(0x2A, [0, 0, x >> 8, x & 255])
        self.command(0x2B, [0, 0, y >> 8, y & 255])
        self.cs.value(0)
        try:
            self.dc.value(0)
            self.spi.write(b'\x2c')
            self.dc.value(1)
            # Sin copia ni intercambio de bytes; CS sigue bajo en todo el envio.
            for start in range(0, len(self.buffer), 4096):
                self.spi.write(self._view[start:start + 4096])
        finally:
            self.cs.value(1)

    def close(self):
        self.cs.value(1)
        self.spi.deinit()
