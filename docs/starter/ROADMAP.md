# AEOS Starter — roadmap vivo

Fuente normativa: [AEOS_STARTER_MVP_PLAN.md](AEOS_STARTER_MVP_PLAN.md). Issue: [#49](https://github.com/Franchute10/autonomous-agent-economy/issues/49). Plan PR: [#50](https://github.com/Franchute10/autonomous-agent-economy/pull/50). Spike técnico: [S0-03](S0-03_TECHNICAL_SPIKE.md).

**Corte:** 2026-11-25 (America/Lima).  
**Estado global:** IN_PROGRESS — dirección del producto confirmada; selección/provisión técnica pendiente.  
**Fecha objetivo:** 2026-12-24, confirmada como objetivo sujeto a los gates del plan.  
**Presupuesto autorizado:** USD 0 hasta aprobación expresa.

| ID | Semana | Entrega | Estado | Evidencia / salida |
|---|---:|---|---|---|
| S0-01 | 0 | Baseline GitHub, ramas y riesgos | DONE | AEOS main eaa8c525; LIVE de2d211b; motor main/ramas comparados; plan documenta divergencia |
| S0-02 | 0 | Alcance Starter y exclusiones | DONE | Plan integrado en main mediante PR #50 / commit db041a62; decisiones de producto confirmadas en DECISION_LOG.md |
| S0-03 | 0 | Confirmar departamento, despliegue, auth, DB y modelo | IN_PROGRESS | Supabase healthy; private RLS probe 7/7 PASS; Pages HTTP 200; Workers Free confirmed; Worker v6 smoke 200/200/401. Valid Auth, tenant authorization, DB from Worker and E2E remain unverified. |
| S1-01 | 1 | Branch de implementación desde main e integración selectiva | TODO | No iniciar hasta cerrar S0-03 y revisar CI/PR |
| S1-02 | 1 | Auth, usuario, organización y membership | TODO | Registro/login y creación de tenant |
| S1-03 | 1 | Aislamiento multi-tenant PostgreSQL/RLS | TODO | Tests cross-tenant sobre PostgreSQL real |
| S1-04 | 1 | Perfil empresarial y documentos | TODO | CRUD y artefactos aislados por tenant |
| S1-05 | 1 | UI inicial desplegada | TODO | URL staging usable |
| S2-01 | 2 | Agent Registry Starter | TODO | Definiciones/versiones/capacidades/límites |
| S2-02 | 2 | Model Gateway (un proveedor) | TODO | Llamada real desde entorno controlado |
| S2-03 | 2 | Tool Gateway allowlisted | TODO | Schemas, autorización y auditoría |
| S2-04 | 2 | Runtime durable | TODO | Persistencia, lease, timeout, retry y recuperación |
| S2-05 | 2 | Orchestrator v1 | TODO | Instrucción → plan estructurado → ejecución autorizada |
| S2-06 | 2 | Centro de trabajo | TODO | Lista y detalle de tareas |
| S3-01 | 3 | Un workflow departamental completo | TODO | Comercial (confirmado); un único departamento plenamente operativo en v0.1 |
| S3-02 | 3 | Evidencia y conocimiento | TODO | Fuentes y artefactos persistidos |
| S3-03 | 3 | Aprobaciones humanas | TODO | Aprobar/rechazar con auditoría |
| S3-04 | 3 | Historial y recuperación | TODO | Retomar sin duplicar efectos |
| S3-05 | 3 | Consumo y límites | TODO | Registro de uso y bloqueo de exceso |
| S4-01 | 4 | Hardening funcional | TODO | Seguridad, errores, idempotencia y permisos |
| S4-02 | 4 | E2E PostgreSQL en staging | TODO | Recorrido completo probado |
| S4-03 | 4 | Piloto cerrado en Perú | TODO | 2–3 usuarios/empresas; evaluación |
| S4-04 | 4 | Release Starter v0.1 | TODO | URL, guía, changelog y soporte |

## Cadencia de control
- Máximo dos tareas técnicas activas en paralelo.
- Cada hito DONE exige issue/PR, SHA, CI, pruebas con denominador y evidencia.
- BLOCKED más de medio día: documentar causa, alternativa y decisión requerida.
- Si el hito S2-05 no logra ejecución real desde UI al 11-12-2026, congelar ampliaciones y reducir alcance.
- Actualizar este archivo en cada cambio de estado; nunca marcar DONE por planificación o código sin validación.
- No crear proyectos, Workers, bindings ni contratar servicios hasta revisar el spike y respetar el presupuesto autorizado de USD 0.

## 2026-11-25 — RLS y primera interfaz estática

2026-11-25: private PostgreSQL RLS spike migration applied only in dedicated aeos-starter project (source commit 77d155925f8e4121d637080a9af02fcb130a29a7, test 5800a7ad117856a14a44ab79c846353707918851). Test with SET LOCAL ROLE authenticated and synthetic JWT sub claims: 7/7 PASS (A own and cross-tenant, write privileges denied, B own and cross-tenant, unknown subject, anonymous grants). Transaction rolled back; 0 rows persisted; RLS enabled and forced; security advisor 0 lints. This is a private probe using owner identity, not production organization membership or Auth JWT verification. Cloudflare subscriptions GET denied HTTP 403 (missing billing:read); account entitlements did not establish Workers plan. Do not deploy metered Workers or invoke AI until free entitlement is verified. To deliver an early visual checkpoint, isolated Cloudflare Pages static-only project aeos-starter-preview created from the GitHub branch, build root spikes/starter_s0_03/preview, automatic production and preview deploys disabled. Manual deployment 264d0cc8-5c6d-4e6e-8e4f-bf98ccac6106 at SHA 2373804b0882963d0c456f590c316474a45d5893: all five Cloudflare stages succeeded. Deployment URL https://264d0cc8.aeos-starter-preview.pages.dev; independent HTTP check blocked by DNS in local execution and web tool could not access URL. Static asset requests free under both plans (https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/); no Pages Functions, paid services, billing upgrades, database credentials, model calls, or customer data. Preview is not a functioning SaaS or API. No other projects touched. Next: validate URL in browser, verify Workers free entitlement through dashboard or Billing Read, then isolated Python runtime deployment and DB connectivity; no metered operation before verified zero-cost path.


## Actualización operativa — 2026-11-27 (America/Lima)

- **Main:** PR #51 y PR #52 integrados; head `4a6979c5d1e15eba22df246b8d5c0c4a8d5deb53`; push CI run [46098462896](https://github.com/Franchute10/autonomous-agent-economy/actions/runs/46098462896) — PASS.
- **S0-03:** sigue IN_PROGRESS. No marcar autenticación real, tenant authorization, conexión PostgreSQL desde Worker ni E2E como verificados. Workers Free y gasto incremental USD 0 siguen vigentes.
- **AEOS-ARCH-001 / Issue #53:** IN_PROGRESS en rama `docs/aeos-arch-001-agent-quality-security-20261128`, creada desde el main anterior `4a6979c5d1e15eba22df246b8d5c0c4a8d5deb53`. Scope documental: calidad, contrato de skills, evaluaciones reproducibles y matriz de seguridad.
- La arquitectura y los tests documentados no equivalen a implementación de runtime, memoria, autorización ni evaluador. Después del PR de Issue #53, el siguiente trabajo seguirá el roadmap sin cerrar S0-03 por inferencia.
