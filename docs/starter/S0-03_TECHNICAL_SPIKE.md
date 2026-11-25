# S0-03 — Spike técnico de despliegue, identidad, datos y modelo

**Fecha:** 2026-11-24 (America/Lima)  
**Estado:** descubrimiento técnico completado; aprobación de stack y aprovisionamiento pendientes.  
**Alcance:** inventario de solo lectura y prueba ASGI local aislada (2026-11-25). No se creó ni modificó infraestructura, no se desplegó código y no se ejecutó inferencia.

## 1. Decisiones de producto ya confirmadas

- Mercado inicial: Perú.
- Producto: un único AEOS Starter SaaS; sin tiers Growth/Business ni billing recurrente en v0.1.
- Autonomía: supervisada.
- Catálogo: todos los departamentos visibles; solo uno tendrá un workflow completo en v0.1.
- Primer departamento operativo: Comercial.
- Fecha objetivo: 2026-12-24, como objetivo sujeto a los gates, no como garantía.
- Presupuesto incremental autorizado: USD 0 hasta aprobación expresa.

Estas decisiones cierran el checkpoint de producto. No autorizan por sí solas gastos, upgrades, creación de proyectos ni despliegues.

## 2. Evidencia de infraestructura consultada

### Cloudflare

- La integración API respondió correctamente a la consulta de identidad y al listado de cuentas. La conexión de Cloudflare está operativa para llamadas API de solo lectura; el aviso de configuración del navegador no equivale a una pérdida de autenticación del conector.
- Se encontró infraestructura Cloudflare existente de otros trabajos, pero no un despliegue AEOS dedicado.
- En el inventario consultado no hay configuraciones AEOS de D1, Queues, Workflows ni Hyperdrive. No se crearon recursos.

### Supabase

- La organización conectada está en el plan Free.
- No existe un proyecto dedicado a AEOS. Los proyectos existentes corresponden a otros trabajos y no deben reutilizarse.
- Se requiere un proyecto separado para AEOS. Antes de crearlo se debe consultar el coste y confirmar la organización; no se creó ningún proyecto ni se ejecutó SQL.

## 3. Compatibilidad técnica verificada en documentación oficial

| Capacidad | Evidencia oficial | Resultado para AEOS |
|---|---|---|
| FastAPI en Python Workers | https://developers.cloudflare.com/workers/languages/python/packages/fastapi/ | Compatible mediante el servidor ASGI de Workers. La guía usa Python 3.13 o superior y el flag python_workers. |
| Workflows desde Python Workers | https://developers.cloudflare.com/workflows/python/ | Hay soporte y ejemplos de WorkflowEntrypoint en Python; permite pasos durables, reintentos y recuperación. El visualizador de diagramas del dashboard aún no representa Python Workflows. |
| PostgreSQL desde Python Workers | https://developers.cloudflare.com/hyperdrive/examples/python-workers/ | Hyperdrive admite PostgreSQL; drivers verificados: asyncpg (recomendado), pg8000 y psycopg. |
| Supabase + Hyperdrive | https://developers.cloudflare.com/workers/databases/third-party-integrations/supabase/ | Cloudflare documenta la conexión directa a Supabase Postgres mediante Hyperdrive. |
| Next.js en Cloudflare | https://developers.cloudflare.com/workers/framework-guides/web-apps/nextjs/ | Cloudflare recomienda vinext como ruta predeterminada; es una reimplementación de la superficie API de Next.js sobre Vite, por lo que requiere una prueba de compatibilidad antes de adoptarlo. |
| Workers AI | https://developers.cloudflare.com/workers-ai/platform/pricing/ | La asignación gratuita documentada es 10,000 Neurons por día. En Workers Free el exceso falla; Workers Paid cobra el exceso y tiene una tarifa base. |

Cloudflare documenta que GLM-4.7-Flash está disponible en Workers Free y admite function calling. Es un candidato para el primer Model Gateway, no una selección aprobada ni una prueba de calidad. No se llamó al modelo.

## 4. Arquitectura candidata para S0-03

Esta es una recomendación técnica para revisar; todavía no es una decisión aceptada:

1. **Frontend:** Next.js/React en Cloudflare Workers mediante vinext, condicionado a un smoke de compatibilidad. Si una dependencia crítica no funciona, usar React estático en Pages sin alterar el dominio ni la API.
2. **API:** FastAPI en un Python Worker de Cloudflare.
3. **Runtime durable:** Cloudflare Workflows desde Python Workers. Mantener la lógica AEOS y sus estados en el dominio; Workflows ejecuta/reintenta pasos, pero no sustituye gobernanza, permisos, idempotencia ni ledger.
4. **Datos:** nuevo proyecto Supabase PostgreSQL exclusivo para AEOS, conectado desde Python Worker por Hyperdrive. Mantener SQLAlchemy/Alembic y PostgreSQL real; D1 no sustituye este requisito de PostgreSQL/RLS.
5. **Identidad:** Supabase Auth. El backend valida JWT; la identidad y membresía de organización se resuelven en servidor. Para conexiones SQL directas, configurar el contexto de usuario dentro de cada transacción y probar RLS con dos tenants. No confiar en organization_id enviado libremente por el navegador.
6. **Modelo:** Cloudflare Workers AI detrás del ModelPort existente. Evaluar GLM-4.7-Flash con límites estrictos y solo dentro de la cuota gratuita disponible. Si se agota la cuota o la calidad no alcanza, detener la ejecución; no hacer upgrade ni consumir un proveedor pagado sin autorización.
7. **Archivos:** decidir entre Supabase Storage y R2 en S1-04; no es necesario bloquear el spike de runtime por esta elección.

## 5. Riesgos y comprobaciones pendientes

- La guía de FastAPI para Python Workers usa Python 3.13+. El proyecto debe probar sus dependencias y adaptar el entorno de ejecución sin romper el soporte local.
- La ruta vinext para Next.js debe superar un smoke de rutas, autenticación, cookies/sesión, cargas y despliegue antes de adoptarse.
- Hyperdrive aún no está configurado. Su conexión a un proyecto AEOS nuevo debe probarse con PostgreSQL real, migración Alembic y RLS.
- La estrategia de RLS para SQL directo debe probar aislamiento cross-tenant y evitar que el contexto de usuario se filtre entre conexiones reutilizadas.
- No se ha verificado el plan exacto de Workers de esta cuenta ni el consumo diario actual de Workers AI. La cuota gratuita de documentación no se debe tratar como saldo disponible confirmado.
- No se ha ejecutado una inferencia ni un test E2E. La compatibilidad documentada no demuestra rendimiento, calidad del modelo ni readiness de producción.
- La arquitectura base AEOS exige primero una prueba determinista con executor falso; la integración real de LLM viene después de superar ese gate.

## 6. Próximo paso y criterio de salida

El propietario debe aprobar o corregir la arquitectura candidata. Después:

1. Consultar el coste de un proyecto Supabase nuevo en la organización seleccionada; no crearlo si el coste no es USD 0 sin una aprobación específica.
2. Si el coste es USD 0 y el propietario confirma la organización, crear un proyecto AEOS aislado y esperar ACTIVE_HEALTHY.
3. Crear solo los recursos mínimos de staging: Worker API Python, Workflow y Hyperdrive; no tocar Workers existentes.
4. Probar FastAPI health check, conexión PostgreSQL, migración Alembic, JWT y RLS cross-tenant. Primero con executor falso.
5. Probar el Model Gateway con un único modelo solo cuando el uso gratuito esté confirmado y con límite por ejecución; registrar tokens/neurons y resultado.
6. Actualizar roadmap y test ledger con SHA, URL de staging, comandos, denominadores y evidencias. No marcar S0-03 DONE antes de esas pruebas.

**Resultado de esta sesión:** el conector Cloudflare está operativo; la plataforma es técnicamente viable para alojar AEOS Starter con Supabase como PostgreSQL/Auth, pero la infraestructura AEOS aún no existe. No hubo gasto, despliegue, modificación de recursos ni llamada a un modelo.

## 7. Avance 2026-11-25 (America/Lima)

- Supabase Management API cotizó un proyecto nuevo en la organización existente: USD 0 mensuales. Es una cotización puntual de creación, no una garantía de todos los consumos futuros. Se solicitó consultar el costo sin crear el proyecto; falta confirmación del propietario para aprovisionarlo. No se tocaron proyectos de terceros.
- PR #51: dos checks de GitHub Actions completados con éxito para el SHA 8951ee99b6a2c6c691f89a7763d65f3889d60c30; evidencia en [push CI](https://github.com/Franchute10/autonomous-agent-economy/actions/runs/45526510310) y [PR CI](https://github.com/Franchute10/autonomous-agent-economy/actions/runs/45526546146). No extrapolar el resultado al nuevo head.
- Se ejecutó un probe ASGI local, código en [health_smoke.py](../../spikes/starter_s0_03/health_smoke.py), commit 9642f2ae957e7f5ac0c93eb1553c34c36f0669b9. Python 3.13.5, FastAPI 0.128.2, httpx 0.28.1, Starlette 0.50.0. Comando reproducible tras instalar FastAPI==0.128.2 y httpx==0.28.1 en un entorno aislado: `python spikes/starter_s0_03/health_smoke.py`. Resultado 4/4 PASS: liveness HTTP 200, readiness HTTP 503 mientras faltan dependencias, POST /tasks HTTP 404, POST /healthz HTTP 405. SHA256 del archivo probado: f2c5182f96f44871d01bc2549c9406288cbcf2bf6cf2018ee6f3a3648e407e70. No se modificaron dependencias del Core.
- El entorno local de ejecución no resolvió github.com; no fue posible clonar ni correr una suite completa del repositorio aquí. El probe se ejecutó como archivo aislado, y se verificó su contenido tras subirlo a GitHub.
- S0-03 sigue IN_REVIEW/BLOCKED en aprovisionamiento. Falta confirmar creación gratuita, validar plan/cuota Cloudflare, desplegar y probar conexión PostgreSQL, auth y RLS. No se ha probado Workers, Hyperdrive ni IA en vivo.


## 8. Provisioning evidence

2026-11-25: owner explicitly authorized isolated Supabase aeos-starter in São Paulo at USD 0/month, no upgrades or additional charges. Quote rechecked at USD 0; project created, ACTIVE_HEALTHY verified independently. Management SQL SELECT 1 returned connectivity=1, PostgreSQL 17.12, database postgres. Security advisor returned zero lints on empty project. No application schema, auth flow, Cloudflare connection, or RLS tested yet. Other projects untouched.
Next: validate free Cloudflare entitlement and deploy isolated health probe; verify actual PostgreSQL connection from runtime before closing S0-03.
