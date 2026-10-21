# TRANSFERENCIA AURA — publicación técnica

- ID: AURA-02/SENSORES-PUB-20261021.
- Fecha: 21/10/2026.
- Responsable: AURA-02 Firmware. Destino: Dirección y Validación.
- Objetivo: publicar fuentes, pruebas e instrucciones de integración SCD41/BME280.
- Estado: [VERIFICADO EN ORDENADOR] 117 pruebas; [PENDIENTE] validación física integrada y aprobación de Dirección.

## Entregables y evidencia

Fuentes MicroPython v0.11.0 basadas en v0.10.1; staging e instalador USB; CRC SCD41; lectura BME280 no bloqueante durante conversión; reintentos; datos parciales sin simulación; pruebas y guía Thonny. Se conserva la versión histórica del repositorio sin reemplazar sus archivos.

## Riesgos y pendientes

No instalar como actualización OTA: el contrato instalado aún no admite cuatro nombres nuevos. El instalador USB verifica base y protege configuración; no garantiza recuperación ante cortes de alimentación. La app iPhone v0.5 requiere adaptación a null. No se han realizado ensayos físicos de esta integración ni se afirma que esté instalada.

## Relevo y actualización propuesta

Próxima acción: instalación controlada y protocolo de aceptación de LEEME_THONNY.md. Criterio: ambos sensores midiendo, Offline operativo, táctil/calibración conservados y errores/recuperación documentados. [PROPUESTO] Registrar código publicado y pruebas de host aprobadas; mantener AURA-003/004/005 en curso hasta validación física y consolidación de AURA-00. Publicar código no equivale a aprobación del estado global.
