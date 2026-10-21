"""Arco e iconos vectoriales pequenos para framebuffer, sin imagenes externas."""


class Widgets:
    def __init__(self, fb):
        self.fb = fb
        # Calcular una sola vez los tramos del anillo. Hueco inferior de 90 grados.
        self.arc_spans = []
        outer, inner = 82, 74
        for dy in range(-outer, outer + 1):
            start = None
            for dx in range(-outer, outer + 2):
                r2 = dx * dx + dy * dy
                inside = (dx <= outer and inner * inner <= r2 <= outer * outer
                          and (dy <= 0 or abs(dx) >= dy))
                if inside and start is None:
                    start = dx
                elif not inside and start is not None:
                    self.arc_spans.append((120 + start, 141 + dy, dx - start))
                    start = None

    def arc(self, color):
        for x, y, width in self.arc_spans:
            self.fb.hline(x, y, width, color)

    def line(self, x0, y0, x1, y1, color):
        # Bresenham con hline para compartir las mismas primitivas de dibujo.
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        error = dx + dy
        while True:
            self.fb.hline(x0, y0, 1, color)
            if x0 == x1 and y0 == y1:
                break
            twice = error * 2
            if twice >= dy:
                error += dy
                x0 += sx
            if twice <= dx:
                error += dx
                y0 += sy

    def thermometer(self, cx, y, color):
        self.fb.fill_rect(cx - 2, y + 2, 5, 13, color)
        self.fb.hline(cx - 1, y + 1, 3, color)
        for row, width in enumerate((5, 7, 9, 9, 7, 5)):
            self.fb.hline(cx - width // 2, y + 13 + row, width, color)
        for dy in (4, 8):
            self.fb.hline(cx + 4, y + dy, 3, color)

    def droplet(self, cx, y, color):
        for row in range(19):
            if row < 12:
                half = row // 2
            else:
                half = (18 - row) // 2 + 2
            self.fb.hline(cx - half, y + row, 2 * half + 1, color)

    def leaf(self, cx, y, color):
        # Contorno de hoja y nervio central, como en la referencia.
        outline = ((-7, 16), (-9, 11), (-8, 6), (-4, 3), (2, 1),
                   (9, 0), (9, 7), (7, 13), (3, 17), (-2, 18), (-7, 16))
        for i in range(len(outline) - 1):
            a, b = outline[i], outline[i + 1]
            self.line(cx + a[0], y + a[1], cx + b[0], y + b[1], color)
        self.line(cx - 10, y + 21, cx + 6, y + 4, color)
        self.line(cx - 2, y + 13, cx - 4, y + 7, color)
        self.line(cx + 2, y + 9, cx + 6, y + 10, color)
