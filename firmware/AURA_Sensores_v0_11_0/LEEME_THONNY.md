# AURA Sensores v0.11.0 — entrega para ensayo

21/10/2026. Base real localizada: AURA_OTA_v0_10_1/firmware, archivos de Work y evidencia del 20/10/2026. El chat «App AURA» documenta v0.10.1 instalada y confirmación del usuario de pantalla/táctil. Esto es evidencia histórica, no una nueva lectura de la placa hoy. El instalador contrasta todos los módulos de esa base antes de escribir. No se parte de v0.6 ni se afirma que v0.11.0 esté instalada.

## Qué hace

- CO₂: SCD41 0x62. Temperatura/humedad: BME280 0x76; si falla o caduca, usa T/RH reales del SCD41 e identifica la fuente en API. Presión: BME280, en hPa absolutos (Pa/100, sin corrección a nivel del mar).
- Bus compartido SoftI2C SDA GPIO8 / SCL GPIO9, 100 kHz, timeout de reloj de 2000 µs. No cambia SPI, orientación horizontal ni calibración.
- SCD41: detener → esperar 500 ms → modo periódico → esperar 5 s → consultar disponibilidad → leer. Verifica longitud y CRC de cada palabra, incluido el estado. No cambia ASC, offset, altitud ni calibración forzada.
- BME280: chip ID 0x60; coeficientes del sensor; conversión forzada x1 por pasos, sin las esperas del driver original. Periodo aproximado 2 s. SCD41 aproximadamente 5 s. El intervalo del menú conserva su función de refresco/historial, no acelera físicamente el SCD41.
- Inicio sin muestras: `--`. Error: invalida de inmediato ese sensor. Más de 15 s desde última muestra: caducado. Error o 20 s sin muestra: reinicialización con reintento a los 10 s. Un sensor puede funcionar aunque el otro falle.
- Pantalla, gráficas y web aceptan valores ausentes. Las gráficas dejan huecos en los errores. No se sustituyen por escenarios, ceros inventados ni últimas muestras presentadas como actuales. demo.py permanece como archivo histórico de la base, pero main.py no lo importa.
- La lectura sigue sin Wi-Fi, NTP ni API. No se usa Internet para medir. Las esperas de conversión no bloquean la interfaz; las transacciones I2C siguen siendo síncronas y breves. Las esperas de red/OTA ya existentes permanecen: no se promete latencia máxima de toda la interfaz sin medirla en placa.

## Carga con Thonny

1. Haz copia privada de todos los archivos del ESP32 en tu ordenador, incluidos `boot.py`, Wi-Fi, JSON y configuración. No publiques esos archivos. Deja que el arranque OTA anterior termine durante al menos 60 s y detén AURA con Stop/Ctrl+C.
2. Copia **solo la carpeta `_aura_sensors` completa a la raíz del ESP32**, con ese mismo nombre. Contiene 10 módulos y manifest.json. NO copies `firmware/`, `regression_tests/` ni su `boot.py`: son referencia y pruebas en ordenador. NO sobrescribas `config.py`, `touch_calibration.json`, ajustes, Wi-Fi ni el cargador OTA.
3. Abre el archivo **local** `instalar_thonny.py` con el intérprete MicroPython del ESP32 y pulsa F5. No lo guardes como main.py. Comprueba hashes de TODOS los módulos de v0.10.1, configuración, staging y ausencia de `.mpy` que puedan ocultar fuentes. Si indica `Base differs`, detente y conserva la salida: hay que revisar esos cambios antes de integrar; no fuerces ni formatees.
4. El instalador respalda los archivos que sustituye en `/aura_before_sensors_v0110`, incluido el driver BME280 anterior si existía. Después verifica los nuevos archivos y los archivos protegidos. Un fallo de escritura ordinario intenta restaurar el programa anterior. No cubre cortes de corriente ni garantiza recuperación si falla también la restauración. No desconectes durante la copia.
5. Cuando indique archivos instalados y verificados, pulsa RESET/EN. Debe mostrar **v0.11.0**, mantener orientación, calibración, Wi-Fi y ajustes. Al principio puede mostrar `--`; el primer CO₂ necesita varios segundos. Si Thonny conserva módulos antiguos en RAM, el reinicio físico los recarga.
6. No borres el respaldo. El instalador se niega a reutilizarlo para no sobrescribir el historial. El cargador OTA no se ha cambiado, y este paquete no se ha publicado. **Esta entrega se instala por USB:** el contrato OTA actual admite 27 módulos y no incluye los cuatro controladores nuevos. Una futura distribución OTA requiere revisar el contrato y su recuperación antes de publicar.

## Prueba de aceptación en la placa (PENDIENTE)

- Registrar fecha, versión visible y `os.uname()` en Thonny. Confirmar menú, botones en las cuatro zonas, orientación y calibración tras dos reinicios. No recalibrar si ya responde correctamente.
- En Offline comprobar CO₂, T/RH y presión durante 10 minutos, con cambios reales y navegación sensible al tacto. Registrar observaciones y errores. Los valores antiguos 1369 ppm, 22.6 °C o 941.4 hPa son ejemplos de evidencia previa: **no tienen que repetirse exactamente**.
- Con Wi-Fi disponible, consultar `/api/measurements`: `demo:false`, `sources.temperature=bme280`, `sources.co2=scd41`; presión en hPa. Los valores ausentes son JSON null; `sensors` explica estado, error y edad.
- Los campos `field_age_ms` contienen edad real por métrica. `age_ms` es la mayor edad entre métricas actuales, null si no hay ninguna; `sample_uptime_ms` se deriva de esa edad. `sample_utc` es null, porque los sensores no se capturan simultáneamente. El reloj local continúa separado. No tratar el instante de refresco de pantalla como instante de captura.
- Con alimentación retirada, preparar una prueba con un sensor ausente y volver a encender. Confirmar que el otro sigue midiendo y que pantalla/menú funcionan. Restaurar el montaje sin tensión y confirmar recuperación tras reinicio. La recuperación automática sin reiniciar está simulada en ordenador; una prueba física controlada del fallo/reintento sigue pendiente. No hace falta manipular conexiones bajo tensión.
- Confirmar que Wi-Fi, touch_calibration.json, aura_settings.json y config.py siguen iguales al respaldo. El instalador verifica hashes localmente sin imprimir secretos.

**Compatibilidad iPhone:** la app v0.5 exige números para todas las métricas. Puede mostrar error al arrancar, caducar datos o fallar un sensor porque ahora recibe null. La web y TFT sí lo gestionan. Adaptar la app a datos parciales queda pendiente; esta entrega no modifica la app ni inventa cifras para satisfacer su decodificador.

## Diagnóstico

`SENSORES: REVISAR` no equivale a ausencia de los dos sensores. Consulta `sensors` en la API. En Offline puedes detener AURA y ejecutar desde Thonny (no guardar como main.py):

```python
from sensor_source import SensorSource
import time
source = SensorSource()
last = time.ticks_ms()
try:
    while True:
        now = time.ticks_ms()
        source.poll(now)
        if time.ticks_diff(now, last) >= 2000:
            print(source.snapshot(now))
            last = now
        time.sleep_ms(20)
except KeyboardInterrupt:
    pass
```

Después pulsa RESET/EN para volver al panel. No ejecutes dos consumidores simultáneos del SCD41. ENODEV: revisar con alimentación retirada SDA8/SCL9, GND, 3V3 y el montaje declarado BME280 CSB→3V3 / SDO→GND. No modificar TFT/táctil. La alimentación/pull-ups y la exactitud metrológica requieren ensayo físico, no las prueban estos tests.

## Reversión manual

Detén AURA. Copia desde el respaldo privado del ordenador los archivos originales sustituidos; `main.py` al final. Alternativamente usa `/aura_before_sensors_v0110/originals.json`: cada archivo con hash se restaura desde esa carpeta; los que figuren null no existían antes y pueden retirarse. Restaura también bme280_float.py anterior si se había sustituido. No toques archivos de configuración ni el cargador. Reinicia y confirma v0.10.1. Una interrupción de la instalación USB requiere esta revisión por Thonny; el diario OTA no cubre este cambio manual.

## Pruebas en ordenador

Desde la carpeta de esta entrega:

```sh
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s regression_tests -v
python3 -m compileall -q firmware instalar_thonny.py
```

El entorno de prueba sustituye periféricos MicroPython y las funciones de tiempo. Se conservan las regresiones previas, con adaptación de la fuente de datos, mocks I2C y lista de módulos modificados. No son ensayos de hardware ni medición de latencia.

## Fuentes

- Sensirion, SCD4x datasheet v1.7 (abril 2025), secciones 3.6, 3.9.2 y CRC: https://sensirion.com/media/documents/48C4B7FB/67FE0194/CD_DS_SCD4x_Datasheet_D1.pdf
- Driver BME280 robert-hh: https://github.com/robert-hh/BME280/blob/master/bme280_float.py (blob 1e2218cd88cc5595f0eabd35a246f59dd2448cd9). Licencia y atribuciones preservadas. Cambios: importar const explícitamente y rechazar presión/calibración inválida en lugar de rellenarla; no limitar T/P artificialmente. El adaptador evita su lectura bloqueante; no se ha podido comprobar identidad con la copia concreta que utilizó el usuario en Thonny.
- Repositorio principal consultado: https://github.com/owwys/Proyect-AURA (README conserva estado histórico v0.8.1/v0.9). Distribución OTA consultada: https://github.com/owwys/aura-updates ; evidencia local y chat App AURA documentan instalación posterior v0.10.1 del 20/10.
