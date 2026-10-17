# AURA Display — paquete histórico declarado v0.9

**Estado del repositorio: PUBLICACIÓN PARCIAL — NO INSTALABLE TODAVÍA.**

Archivo histórico recibido el 17/10/2026. El ZIP original privado tiene SHA-256:
`193690650ba3a7dba2d34dcaebb306bb653193c0408d7756142033c99dde0b7b`.

La carpeta contiene actualmente algunos módulos originales sin secretos (`boot.py`, `config.py`, `demo.py`, `history.py`, `tft_environment.py`), parámetros locales no confidenciales, ejemplos Wi-Fi y esta documentación. **Siguen faltando el ejecutable `main.py`, `aura_app.py`, controladores de pantalla y otros módulos. No cargar esta carpeta como firmware completo.**

El paquete externo saneado preparado conserva 85 archivos. Excluye `wifi_config.py` y `wifi_settings.json` con valores privados, registros y metadatos locales. La configuración de Wi-Fi debe crearse localmente y nunca publicarse.

**Discrepancia de versión:** el paquete se llama v0.9; `config.py` indica `FIRMWARE_VERSION = 'v0.8.1'`. No se ha modificado la constante.

**Pruebas estáticas del paquete saneado (17/10/2026):** 78 fuentes Python parseados sin errores con CPython; `DemoSource` produce una secuencia cíclica, y `History` conserva los últimos tres registros en una prueba simple. Estas comprobaciones **no demuestran ejecución en MicroPython ni pruebas físicas de TFT/táctil/Wi-Fi**. Lectura real del SCD41 no implementada en este firmware de demostración.

**[PENDIENTE]** completar la subida de todos los fuentes saneados, contrastar integridad, probar carga y arranque en ESP32-S3 y documentar evidencia fechada.
