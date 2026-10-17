"""Historial circular local; nunca escribe muestras en flash."""
METRICS = (('co2', 'CO2', 'ppm'), ('temperature', 'TEMPERATURA', 'C'),
           ('humidity', 'HUMEDAD', '%'), ('pressure', 'PRESION', 'hPa'))

class History:
    def __init__(self, capacity=120):
        if capacity < 2:
            raise ValueError('Capacidad insuficiente')
        self.rows = [None] * capacity
        self.next = 0
        self.count = 0

    def add(self, seconds, data):
        self.rows[self.next] = (seconds,) + tuple(data[m[0]] for m in METRICS)
        self.next = (self.next + 1) % len(self.rows)
        self.count = min(self.count + 1, len(self.rows))

    def series(self, key):
        column = [m[0] for m in METRICS].index(key) + 1
        start = (self.next - self.count) % len(self.rows)
        return [(self.rows[(start+i) % len(self.rows)][0],
                 self.rows[(start+i) % len(self.rows)][column]) for i in range(self.count)]
