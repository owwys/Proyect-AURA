"""Escenarios deterministas: no importa ni intenta detectar sensores."""
SCENARIOS = (
    (650, 22.5, 48, 1013),
    (780, 22.6, 49, 1013),
    (950, 22.7, 50, 1012),
    (1250, 22.8, 51, 1012),
    (1650, 22.9, 52, 1011),
    (1100, 22.7, 50, 1012),
    (720, 22.5, 48, 1013),
)


class DemoSource:
    def __init__(self):
        self.index = 0

    def read(self):
        co2, temp, humidity, pressure = SCENARIOS[self.index]
        self.index = (self.index + 1) % len(SCENARIOS)
        return {'co2': co2, 'temperature': temp, 'humidity': humidity,
                'pressure': pressure, 'demo': True}


def co2_style(value):
    # Umbrales solo para mostrar estados de la interfaz de demostracion.
    if value < 800:
        return 'BAJO', (52, 211, 153)
    if value < 1200:
        return 'MEDIO', (251, 191, 36)
    return 'ALTO', (251, 113, 133)
