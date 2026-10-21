# AURA — Proyecto de monitorización ambiental

AURA One Indoor es un proyecto de monitorización ambiental interior, diseñado con principios **Local-First**, privacidad y funcionamiento local.

## Documentación

- [Firmware histórico y estado de integración](firmware/README.md)
- [Historial de cambios](CHANGELOG.md)
- [Arquitectura](docs/arquitectura.md)
- [Documentación del firmware](docs/firmware.md)
- [Validación](docs/validacion.md)

## Integración de sensores — 21/10/2026

[Fuentes y guía AURA Sensores v0.11.0](firmware/AURA_Sensores_v0_11_0/README.md): base v0.10.1, SCD41/BME280, lectura periódica y datos parciales sin simulación. **117 pruebas en ordenador aprobadas; instalación y ensayo integrado en ESP32 pendientes.** La carga inicial es por USB; esta subida no es una actualización OTA estable.

## Situación histórica — 17/10/2026

El prototipo utiliza ESP32-S3 N16R8 y pantalla ILI9341; SCD41 y BME280 son componentes previstos cuya integración completa no está verificada. El paquete recibido como **AURA Display v0.9** contiene una constante interna **v0.8.1**; esta discrepancia continúa pendiente de aclaración.

## Seguridad

Las configuraciones reales de Wi-Fi no deben publicarse. La visibilidad pública no implica licencia de reutilización: **licencia pendiente de decidir**.

El estado operativo del proyecto y las decisiones validadas se mantienen en el registro central de Google Drive bajo AURA-00.

