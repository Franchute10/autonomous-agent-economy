# AEOS Starter v0.1 — release checklist

No publicar como MVP hasta completar todos los gates obligatorios.

## Producto
- [ ] Un único producto Starter; sin planes Growth/Business ni billing recurrente.
- [ ] Un departamento operativo de extremo a extremo; capacidades no implementadas claramente identificadas.
- [ ] Flujo de usuario completo validado en staging.
- [ ] Guía rápida y canal de soporte definidos.

## Seguridad y datos
- [ ] Auth y recuperación de cuenta probadas.
- [ ] Tenant isolation con PostgreSQL/RLS en todas las tablas privadas.
- [ ] Credenciales solo en secret manager/environment seguro.
- [ ] Documentos privados aislados y URLs de descarga autorizadas.
- [ ] Exportación/eliminación y retención documentadas.
- [ ] No se subieron secretos ni datos personales de clientes al repo público.
- [ ] Acciones externas bloqueadas hasta aprobación humana.

## Runtime y modelos
- [ ] Modelo real vía Model Gateway.
- [ ] Herramientas allowlisted, schema y autorización.
- [ ] Límites de gasto/consumo y timeout.
- [ ] Ejecuciones durables y recuperación tras reinicio.
- [ ] Idempotencia y prevención de acciones duplicadas.
- [ ] Resultados, fuentes y auditoría persistidos.

## Calidad y operación
- [ ] CI verde en SHA de release.
- [ ] PostgreSQL E2E y browser E2E aprobados.
- [ ] Health check, logs, errores y alertas.
- [ ] Backups y restauración probados.
- [ ] URL HTTPS estable.
- [ ] Política de privacidad y condiciones de piloto revisadas.
- [ ] Aceptación del propietario y feedback del piloto registrado.

**Release decision:** NOT RELEASED hasta que los checks anteriores estén marcados con evidencia enlazada.
