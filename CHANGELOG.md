# Historial de documentación y firmware

## 2026-10-21 — Integración SCD41/BME280 v0.11.0 para ensayo

- Código, staging USB/Thonny, pruebas y evidencias en `firmware/AURA_Sensores_v0_11_0/`.
- Base v0.10.1; lectura periódica por estados, CRC SCD41, T/RH BME280 preferentes y presión en hPa.
- Errores y datos caducados como ausentes, con fuente y edad por métrica; sin sustitución por datos simulados.
- [VERIFICADO EN ORDENADOR] 16 pruebas sensores/instalador + 101 de regresión.
- [PENDIENTE] Instalación y ensayo integrado en hardware; adaptación iPhone a datos parciales y contrato OTA ampliado.
- No se reemplazan las fuentes históricas, no se publica una release OTA estable y no se incluyen archivos privados.

## 2026-10-17 — Recepción de paquete declarado AURA Display v0.9

- Recibido ZIP con fuentes de MicroPython.
- [DECLARADO] Identificador externo `AURA_Display_v0_9.zip`.
- [VERIFICADO POR INSPECCIÓN] En el `config.py` del paquete figura `FIRMWARE_VERSION = 'v0.8.1'`.
- [PENDIENTE] Resolver discrepancia v0.9 frente a v0.8.1 y reproducir ejecución en ESP32-S3.
- [PENDIENTE] Completar incorporación del código fuente público saneado al repositorio.
- No se han realizado pruebas sobre hardware en este trabajo.

SHA-256 del ZIP original privado: `193690650ba3a7dba2d34dcaebb306bb653193c0408d7756142033c99dde0b7b`.

