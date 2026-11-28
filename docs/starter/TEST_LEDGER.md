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


## 2026-11-25 — RLS y primera interfaz estática

2026-11-25: private PostgreSQL RLS spike migration applied only in dedicated aeos-starter project (source commit 77d155925f8e4121d637080a9af02fcb130a29a7, test 5800a7ad117856a14a44ab79c846353707918851). Test with SET LOCAL ROLE authenticated and synthetic JWT sub claims: 7/7 PASS (A own and cross-tenant, write privileges denied, B own and cross-tenant, unknown subject, anonymous grants). Transaction rolled back; 0 rows persisted; RLS enabled and forced; security advisor 0 lints. This is a private probe using owner identity, not production organization membership or Auth JWT verification. Cloudflare subscriptions GET denied HTTP 403 (missing billing:read); account entitlements did not establish Workers plan. Do not deploy metered Workers or invoke AI until free entitlement is verified. To deliver an early visual checkpoint, isolated Cloudflare Pages static-only project aeos-starter-preview created from the GitHub branch, build root spikes/starter_s0_03/preview, automatic production and preview deploys disabled. Manual deployment 264d0cc8-5c6d-4e6e-8e4f-bf98ccac6106 at SHA 2373804b0882963d0c456f590c316474a45d5893: all five Cloudflare stages succeeded. Deployment URL https://264d0cc8.aeos-starter-preview.pages.dev; independent HTTP check blocked by DNS in local execution and web tool could not access URL. Static asset requests free under both plans (https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/); no Pages Functions, paid services, billing upgrades, database credentials, model calls, or customer data. Preview is not a functioning SaaS or API. No other projects touched. Next: validate URL in browser, verify Workers free entitlement through dashboard or Billing Read, then isolated Python runtime deployment and DB connectivity; no metered operation before verified zero-cost path.


## 2026-11-27 — smoke checks del Worker y estado de integración

| Check | Resultado | Alcance / límite |
|---|---|---|
| Pages preview | PASS — HTTP 200 | Sitio estático con `noindex,nofollow`; no autentica ni procesa tareas. |
| Worker v6 — preview | PASS | `/health` 200; `/api/v1/capabilities` 200; `/api/v1/me` sin token 401. |
| Worker v6 — producción | PASS | Mismas tres respuestas esperadas; sin token ni datos de clientes. La versión 6 recibe 100% del tráfico. |
| Auth live | NOT VERIFIED | No se comprobó sesión Supabase válida, membership, permisos ni aislamiento multi-tenant. |
| PostgreSQL desde Worker / RLS E2E | NOT RUN | El probe privado 7/7 no sustituye la prueba desde runtime. |
| Model inference / ejecución de agentes | NOT RUN | Deshabilitados para mantener el presupuesto incremental en USD 0. |
| CI PR #51 | PASS | PR run 45554584495 para head `bb3b469a4c42ac075b7e72e53de2bb5f9e246d6d`. |
| CI PR #52 | PASS | PR run 46089162095 para head `41f5cd539e66de80515871dd6b281599d98a74f8`; verificar de nuevo tras cambios de base/head. |

La cuenta Workers Free y la ausencia de método de pago fueron confirmadas por el propietario en el dashboard. Estos GET de smoke se hicieron dentro de los recursos Free existentes; no se activó facturación ni se alteraron secretos.


## 2026-11-28 — S1-02 organización y RLS

| Check | Resultado | SHA / alcance |
|---|---|---|
| GitHub Actions CI | PASS, run #486 | `6c2d4db78c659ccd852f0956933b02fc00b868eb`; Ruff, format, mypy, core/Worker tests y empaquetado según pipeline. | 
| Supabase migrations | PASS | `20261128032248 starter_organizations_memberships_idempotent` y `20261128032620 fix_create_organization_conflict_target`, proyecto Free `aeos-starter`. | 
| SQL sintético transaccional | PASS | Dos usuarios UUID sintéticos; replay idempotente, creación de membership owner, aislamiento A/B y bloqueo de insert directo bajo rol authenticated. `ROLLBACK`; comprobación posterior: 0 organizaciones, 0 memberships y 0 usuarios sintéticos. | 
| Seguridad Supabase | REVIEWED | Una advertencia para la RPC `SECURITY DEFINER`, intencional y restringida a identidad `auth.uid()`, `search_path` fijo y sin SQL dinámico. | 
| API real desde Worker / sesión válida | NOT RUN | No hubo deploy de nueva versión ni sesión de usuario; no afirmar auth E2E. | 

La primera prueba SQL detectó referencia ambigua a `organization_id` en `ON CONFLICT`; se agregó y aplicó una migración correctiva usando la constraint primaria explícita. La prueba completa pasó tras la corrección. No se ejecutó inferencia de modelo ni hubo tráfico de producción.
