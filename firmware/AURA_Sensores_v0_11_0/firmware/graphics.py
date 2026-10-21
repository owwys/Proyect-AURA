"""Fuente retro nativa 8x8 de MicroPython, ampliada sin suavizado."""
import framebuf


class Graphics:
    def __init__(self, fb):
        self.fb = fb
        self.glyph = framebuf.FrameBuffer(bytearray(8), 8, 8, framebuf.MONO_HLSB)

    def measure(self, text, scale=1):
        return len(str(text)) * 8 * scale

    def text(self, text, x, y, color, scale=1):
        if not isinstance(scale, int) or scale < 1:
            raise ValueError('La escala debe ser un entero positivo')
        text = str(text)
        if scale == 1:
            self.fb.text(text, x, y, color)
            return
        for char in text:
            self.glyph.fill(0)
            self.glyph.text(char, 0, 0, 1)
            for gy in range(8):
                for gx in range(8):
                    if self.glyph.pixel(gx, gy):
                        self.fb.fill_rect(x + gx * scale, y + gy * scale,
                                          scale, scale, color)
            x += 8 * scale

    def centered(self, text, y, color, scale=1, x=0, width=240):
        self.text(text, x + (width - self.measure(text, scale)) // 2,
                  y, color, scale)

    def card(self, x, y, w, h, color, radius=8):
        # Esquinas recortadas de radio pequeno, sin depender de ellipse().
        self.fb.fill_rect(x + radius, y, w - 2 * radius, h, color)
        self.fb.fill_rect(x, y + radius, w, h - 2 * radius, color)
        for row in range(radius):
            inset = radius - int((radius * radius - (radius - row) ** 2) ** 0.5)
            self.fb.hline(x + inset, y + row, w - 2 * inset, color)
            self.fb.hline(x + inset, y + h - 1 - row, w - 2 * inset, color)

    def number(self, value, y, color, compact=False):
        if not isinstance(value, int) or not 0 <= value <= 9999:
            raise ValueError('CO2 debe ser un entero de 0 a 9999')
        text = str(value)
        scale = 4 if compact and len(text) == 4 else 5
        self.centered(text, y + (49 - 8 * scale) // 2, color, scale)
