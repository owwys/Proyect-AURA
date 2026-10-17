"""Criterios orientativos de interfaz; no diagnostico ni detector de seguridad.
Fuentes y limites documentados en CRITERIOS.md. Presion no interviene.
"""
def valid(value, low, high):
    return type(value) in (int, float) and low <= value <= high


def assess(data):
    c, t, h = (data.get(k) for k in ('co2', 'temperature', 'humidity'))
    if not (valid(c, 0, 1000000) and valid(t, -40, 85) and valid(h, 0, 100)):
        return 'unknown', 'Datos incompletos'
    if c > 1500:
        return 'concerned', 'Mejora ventilacion'
    if h >= 60:
        return 'concerned', 'Humedad elevada'
    if c >= 1000:
        return 'neutral', 'Revisa ventilacion'
    if t < 18:
        return 'neutral', 'Habitacion fria'
    if t > 24:
        return 'neutral', 'Habitacion calida'
    if h < 30:
        return 'neutral', 'Ambiente seco'
    if h > 50:
        return 'neutral', 'Revisa humedad'
    return 'happy', 'En rango orientativo'
