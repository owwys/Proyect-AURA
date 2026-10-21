"""Geometria TFT; conserva la matriz y los puntos de calibracion verticales."""
from touch import apply

MENU_BUTTON = (272, 6, 40, 28)
BACK_BUTTON = (216, 196, 96, 28)
TREND_BUTTON = (8, 160, 304, 28)
SETTING_INTERVAL = (8, 64, 144, 34)
SETTING_ZONE = (160, 64, 152, 34)
SETTING_SAVE = (8, 112, 144, 34)
CLOCK_FIELDS = (((8,62,52,32),2), ((64,62,52,32),1),
                ((120,62,72,32),0), ((196,62,54,32),3), ((254,62,58,32),4))
CLOCK_PREV, CLOCK_NEXT = (8,108,144,28), (160,108,152,28)
CLOCK_MINUS, CLOCK_PLUS = (8,142,144,28), (160,142,152,28)
CLOCK_APPLY, CLOCK_CANCEL = (8,196,144,28), (160,196,152,28)


def menu_rect(index):
    return (8 + (index % 2)*156, 40 + (index//2)*38, 148, 30)


def portrait_to_landscape(point):
    x, y = point
    return y, 239-x


class LandscapeTouch:
    """Adaptador de presentacion: nunca escribe ni transforma la matriz guardada."""
    def __init__(self, touch):
        self.original = touch

    def __getattr__(self, name):
        return getattr(self.original, name)

    def screen_point(self, raw):
        if self.original.matrix is None:
            return None
        x, y = apply(self.original.matrix, raw)
        if 0 <= x < 240 and 0 <= y < 320:
            return portrait_to_landscape((x, y))
        return None

# Controles del asistente y confirmacion; coordenadas horizontales.
SETUP_SKIP = (8,190,304,32)
WIFI_CANCEL = (8,196,144,28)
WIFI_CONFIRM = (160,196,152,28)
