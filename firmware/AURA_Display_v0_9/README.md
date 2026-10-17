# AURA Display — paquete declarado v0.9

**[PENDIENTE] Publicación incompleta: no instalar directamente esta carpeta como firmware.**

Fuente: archivo `AURA_Display_v0_9.zip` recibido el 17/10/2026. Huella SHA-256 del archivo original privado:

`193690650ba3a7dba2d34dcaebb306bb653193c0408d7756142033c99dde0b7b`

## Módulos publicados

Esta carpeta ya contiene `aura_app.py`, `boot.py`, `config.py`, `demo.py`, `graphics.py`, `history.py`, `tft_environment.py`, `touch.py`, ejemplos de Wi-Fi y algunos archivos de configuración.

**No se han conseguido publicar `main.py` ni `ili9341.py`**: la integración bloqueó los intentos de escritura. También faltan otros módulos necesarios para arrancar el programa. La publicación está incompleta y no se debe considerar ejecutable.

El paquete saneado preparado para publicación elimina las configuraciones privadas `wifi_config.py` y `wifi_settings.json` y los registros locales. El archivo original completo no debe subirse a un repositorio público.

## Versionado y validación

- **[DECLARADO]** El archivo ZIP se identifica como versión v0.9.
- **[VERIFICADO POR INSPECCIÓN]** `config.py` conserva `FIRMWARE_VERSION = 'v0.8.1'`. Discrepancia histórica pendiente.
- **[VERIFICADO ESTÁTICAMENTE]** Los archivos Python del paquete se analizaron sintácticamente sin errores.
- **[PENDIENTE]** Publicación del resto de fuentes, comprobación de imports, carga en MicroPython y ensayos con ESP32-S3, ILI9341 y táctil.
- **[PENDIENTE]** Firmware real del SCD41; `DemoSource` entrega datos simulados.

No confundir una publicación de archivos con una prueba física ni con una aprobación de AURA-00.
