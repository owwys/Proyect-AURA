# AURA — Proyecto de monitorización ambiental

AURA One Indoor es un proyecto de monitorización ambiental interior, diseñado con principios **Local-First**, privacidad y funcionamiento local.

## Documentación

- [Firmware histórico y estado de integración](firmware/README.md)
- [Historial de cambios](CHANGELOG.md)
- [Arquitectura](docs/arquitectura.md)
- [Documentación del firmware](docs/firmware.md)
- [Validación](docs/validacion.md)

## Situación

El prototipo utiliza ESP32-S3 N16R8 y pantalla ILI9341; SCD41 y BME280 son componentes previstos cuya integración completa no está verificada. El paquete recibido como **AURA Display v0.9** contiene una constante interna **v0.8.1**; esta discrepancia continúa pendiente de aclaración.

## Seguridad

Las configuraciones reales de Wi-Fi no deben publicarse. La visibilidad pública no implica licencia de reutilización: **licencia pendiente de decidir**.

El estado operativo del proyecto y las decisiones validadas se mantienen en el registro central de Google Drive bajo AURA-00.
