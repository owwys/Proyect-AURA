"""XPT2046: SPI compartido, toque al soltar y calibracion afin de tres puntos."""
import time
import json
from machine import Pin
import config

TARGETS = ((24, 48), (216, 48), (120, 272))
CHECK_TARGET = (120, 160)


def affine(raw, screen=TARGETS):
    (x1, y1), (x2, y2), (x3, y3) = raw
    det = x1 * (y2-y3) + x2 * (y3-y1) + x3 * (y1-y2)
    if abs(det) < 10000:
        raise ValueError('Puntos insuficientemente separados')
    def coeff(values):
        v1, v2, v3 = values
        return ((v1*(y2-y3)+v2*(y3-y1)+v3*(y1-y2))/det,
                (v1*(x3-x2)+v2*(x1-x3)+v3*(x2-x1))/det,
                (v1*(x2*y3-x3*y2)+v2*(x3*y1-x1*y3)+v3*(x1*y2-x2*y1))/det)
    return coeff([p[0] for p in screen]) + coeff([p[1] for p in screen])


def apply(matrix, raw):
    x, y = raw
    a, b, c, d, e, f = matrix
    return int(round(a*x+b*y+c)), int(round(d*x+e*y+f))


class TapTracker:
    def __init__(self):
        self.started = None
        self.last = None
        self.released = None

    def update(self, raw, pressed, now):
        if pressed:
            self.released = None
            if raw is not None:
                if self.started is None:
                    self.started = now
                self.last = raw
            return None
        if self.started is None:
            return None
        if self.released is None:
            self.released = now
            return None
        if time.ticks_diff(now, self.released) < 40:
            return None
        result = self.last if time.ticks_diff(self.released, self.started) >= 60 else None
        self.started = self.last = self.released = None
        return result


class Touch:
    def __init__(self, display):
        self.spi = display.spi
        self.display_cs = display.cs
        self.cs = Pin(config.TOUCH_CS, Pin.OUT, value=1)
        self.irq = Pin(config.TOUCH_IRQ, Pin.IN, Pin.PULL_UP)
        self.tracker = TapTracker()
        self.matrix = None
        self.calibration_state = 'pending'
        self.tx = bytearray(3)
        self.rx = bytearray(3)
        try:
            with open(config.TOUCH_CALIBRATION_FILE) as source:
                matrix = json.load(source)
            if (len(matrix) == 6 and all(isinstance(v, (int, float)) and abs(v) < 1e6 for v in matrix)
                    and abs(matrix[0]*matrix[4]-matrix[1]*matrix[3]) > 1e-8):
                self.matrix = matrix
                self.calibration_state = 'loaded'
        except (OSError, ValueError, TypeError):
            pass

    def _bus(self, baudrate):
        self.spi.init(baudrate=baudrate, polarity=0, phase=0,
                      sck=Pin(config.SCK), mosi=Pin(config.MOSI),
                      miso=Pin(config.TOUCH_MISO))

    def _axis(self, command):
        self.tx[0] = command
        self.tx[1] = self.tx[2] = 0
        self.cs.value(0)
        try:
            self.spi.write_readinto(self.tx, self.rx)
            return ((self.rx[1] << 8) | self.rx[2]) >> 3
        finally:
            self.cs.value(1)

    def read_raw(self):
        self.display_cs.value(1)
        try:
            self._bus(config.TOUCH_SPI_HZ)
            # Descartar la primera conversion despues de cambiar de canal.
            xs, ys = [], []
            for _ in range(5):
                self._axis(0xD0)
                xs.append(self._axis(0xD0))
                self._axis(0x90)
                ys.append(self._axis(0x90))
            if max(xs)-min(xs) > 160 or max(ys)-min(ys) > 160:
                return None
            xs.sort()
            ys.sort()
            if not 20 < xs[2] < 4075 or not 20 < ys[2] < 4075:
                return None
            return xs[2], ys[2]
        finally:
            self.cs.value(1)
            self._bus(config.SPI_HZ)

    def poll(self):
        pressed = self.irq.value() == 0
        raw = self.read_raw() if pressed else None
        return self.tracker.update(raw, pressed, time.ticks_ms())

    def screen_point(self, raw):
        if self.matrix is None:
            return None
        x, y = apply(self.matrix, raw)
        if 0 <= x < config.WIDTH and 0 <= y < config.HEIGHT:
            return x, y
        return None

    def save(self, matrix):
        # Solo se guarda tras confirmar el cuarto punto de comprobacion.
        self.matrix = matrix
        self.calibration_state = 'unsaved'
        try:
            with open(config.TOUCH_CALIBRATION_FILE, 'w') as target:
                json.dump(matrix, target)
            self.calibration_state = 'saved'
            return True
        except OSError:
            print('Calibracion activa, pero no se pudo guardar en flash.')
            return False
