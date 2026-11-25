# AEOS Starter — test ledger

**Corte:** 2026-11-25. Este registro separa pruebas históricas de AEOS Core, LIVE y Commercial Lead Engine de las futuras pruebas de Starter.

## Evidencia previa consultada

| Componente | Ref/SHA | Resultado reportado | Qué demuestra | Qué NO demuestra |
|---|---|---|---|---|
| AEOS main | eaa8c5255828 | Base de dominio, persistencia y tests en GitHub | Contratos tipados y pruebas de módulos existentes | Runtime, SaaS UI, Model Gateway o release |
| AEOS LIVE | de2d211bc22c | CI reportada 953 passed / 12 skipped en PR #48 (2026-11-22) | Línea LIVE pasa CI; smoke acotado de dos sitios | Starter, PostgreSQL completo, runtime multiagente o ventas |
| AEOS PR #48 | 903236836749 | CI y smoke jobs success | Checks de ese head LIVE | Integración a main o producto SaaS |
| Commercial Lead Engine | a647263bcde2 | 880 passed reportados en validación 2026-11-20 | Tests de motor CLI en esa rama | API, multi-tenancy, SaaS o leads vendibles |
| Commercial Lead Engine | PR #1/#2 | Abiertos/apilados al corte | Propuestas de captura y evaluación de intención | Merge, fuente autorizada universal o utilidad comercial repetible |

## S0-03 — descubrimiento de infraestructura (solo lectura)

| Check | Resultado | Evidencia / límite |
|---|---|---|
| Cloudflare connector/API | PASS — lectura | Identidad y cuenta consultadas; no se modificó ningún recurso. |
| Cloudflare inventory | PASS — lectura | No hay despliegue AEOS dedicado ni configuraciones AEOS de D1, Queues, Workflows o Hyperdrive. |
| Supabase inventory | PASS — lectura | No se encontró proyecto dedicado a AEOS; no se reutilizaron proyectos existentes ni se creó uno nuevo. |
| Compatibilidad de plataforma | REVIEWED | Documentación oficial confirma FastAPI/Python Workers, Workflows Python, Hyperdrive/PostgreSQL y Workers AI. La documentación no sustituye pruebas runtime. |
| Supabase cotización | PASS — lectura | 2026-11-25: proyecto nuevo USD 0/mes; creación pendiente. |
| CI PR #51 (head anterior) | 2/2 checks PASS | SHA 8951ee99b6a2c6c691f89a7763d65f3889d60c30; [push CI](https://github.com/Franchute10/autonomous-agent-economy/actions/runs/45526510310), [PR CI](https://github.com/Franchute10/autonomous-agent-economy/actions/runs/45526546146). |
| Probe ASGI local | 4/4 PASS | Commit 9642f2ae957e7f5ac0c93eb1553c34c36f0669b9; Python 3.13.5; FastAPI 0.128.2, httpx 0.28.1. Ver [S0-03](S0-03_TECHNICAL_SPIKE.md). No es un despliegue. |
| Model Gateway | NOT RUN | No se ejecutó inferencia ni se consumió cuota. |
| Deploy / PostgreSQL / RLS E2E | NOT RUN | No se creó infraestructura ni se desplegó código. |

Estos checks son descubrimiento de entorno y prueba local aislada, no pruebas de aceptación del producto. No cambian el estado de los tests T-001 a T-010.

## Pruebas Starter
Aún no ejecutadas. No declarar PASS hasta registrar SHA, entorno, comando y resultado.

| Test ID | Alcance | Entorno | Estado | Resultado |
|---|---|---|---|---|
| T-001 | Signup/login y creación de organización | Staging | TODO | — |
| T-002 | Tenant isolation y RLS cross-tenant | PostgreSQL staging | TODO | — |
| T-003 | Upload/list/download de documento tenant-scoped | Staging | TODO | — |
| T-004 | Ejecución real de un modelo vía Model Gateway | Staging | TODO | — |
| T-005 | Workflow del departamento inicial end-to-end | Staging | TODO | — |
| T-006 | Approval/reject y audit trail | Staging | TODO | — |
| T-007 | Reinicio worker, recuperación e idempotencia | Staging | TODO | — |
| T-008 | Cuota/consumo y bloqueo de exceso | Staging | TODO | — |
| T-009 | E2E completo desde browser | Staging + PostgreSQL | TODO | — |
| T-010 | Piloto y evaluación de usuario | Perú | TODO | — |

Cada nueva ejecución añade una fila con fecha, repo/rama/SHA, comando, entorno, passed/failed/skipped, link CI/log, evidencia real o sintética y decisión. No sobrescribir fallos históricos.

## 2026-11-25 — Supabase provisioning

2026-11-25: owner explicitly authorized isolated Supabase aeos-starter in São Paulo at USD 0/month, no upgrades or additional charges. Quote rechecked at USD 0; project created, ACTIVE_HEALTHY verified independently. Management SQL SELECT 1 returned connectivity=1, PostgreSQL 17.12, database postgres. Security advisor returned zero lints on empty project. No application schema, auth flow, Cloudflare connection, or RLS tested yet. Other projects untouched.
