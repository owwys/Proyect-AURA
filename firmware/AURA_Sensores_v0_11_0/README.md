# AURA Sensores v0.11.0 — versión de ensayo

Integración SCD41 y BME280 para ESP32-S3 N16R8 con MicroPython, ILI9341 horizontal y táctil XPT2046. Base: v0.10.1. Fecha: 21/10/2026.

- [VERIFICADO EN ORDENADOR] 117 pruebas: 16 sensores/instalador y 101 regresiones.
- [PENDIENTE] Instalación y ensayo conjunto en hardware. No es una publicación OTA estable.
- [LEEME_THONNY.md](LEEME_THONNY.md): carga por USB, verificación de base, respaldo, diagnóstico y reversión.
- `firmware/`: fuentes completas de referencia; NO copiar esta carpeta completa a la placa.
- `_aura_sensors/`: staging de los 10 módulos a instalar (6 modificados y 4 nuevos).
- `instalar_thonny.py`: ejecutar como archivo local desde Thonny después de copiar staging.
- `tests/` y `regression_tests/`: pruebas en ordenador, con periféricos simulados.
- `evidencias/`, `VERIFICACION.md`, `BASE_SHA256.json`, `CAMBIOS.patch` y `SHA256SUMS.txt`: trazabilidad.

CO₂ del SCD41; T/RH preferentes del BME280 con alternativa real del SCD41; presión BME280 en hPa absolutos. Lectura por pasos, CRC SCD41, errores independientes, caducidad y fuentes por métrica. Sin datos simulados en main.py. Conserva configuración, pantalla y calibración táctil.

El cargador instalado admite una lista fija de 27 módulos. Los cuatro nuevos requieren instalación USB; publicarlos aquí no modifica ese contrato. La app iPhone v0.5 necesita admitir null para gestionar calentamiento o fallo de sensores. TFT y web ya admiten datos parciales.

Este directorio contiene solo material técnico revisado para publicación. No incluye configuración Wi-Fi real, calibración privada, respaldos del dispositivo ni el registro interno completo. La licencia general del proyecto sigue pendiente; se conserva la licencia original del driver BME280 en su archivo.

## Pruebas

Desde este directorio:

```sh
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s regression_tests -v
python3 -m compileall -q firmware instalar_thonny.py
```
