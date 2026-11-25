# AEOS Starter — test ledger

**Corte:** 2026-11-24. Este registro separa pruebas históricas de AEOS Core, LIVE y Commercial Lead Engine de las futuras pruebas de Starter.

## Evidencia previa consultada

| Componente | Ref/SHA | Resultado reportado | Qué demuestra | Qué NO demuestra |
|---|---|---|---|---|
| AEOS main | eaa8c5255828 | Base de dominio, persistencia y tests en GitHub | Contratos tipados y pruebas de módulos existentes | Runtime, SaaS UI, Model Gateway o release |
| AEOS LIVE | de2d211bc22c | CI reportada 953 passed / 12 skipped en PR #48 (2026-11-22) | Línea LIVE pasa CI; smoke acotado de dos sitios | Starter, PostgreSQL completo, runtime multiagente o ventas |
| AEOS PR #48 | 903236836749 | CI y smoke jobs success | Checks de ese head LIVE | Integración a main o producto SaaS |
| Commercial Lead Engine | a647263bcde2 | 880 passed reportados en validación 2026-11-20 | Tests de motor CLI en esa rama | API, multi-tenancy, SaaS o leads vendibles |
| Commercial Lead Engine | PR #1/#2 | Abiertos/apilados al corte | Propuestas de captura y evaluación de intención | Merge, fuente autorizada universal o utilidad comercial repetible |

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
