# AEOS — Continuidad vigente
Actualizado: 2026-11-25 (America/Lima). **Prioridad vigente: AEOS Starter MVP**.

## PRIORIDAD ACTUAL — AEOS STARTER MVP

El propietario ha reorientado el trabajo al lanzamiento de un único producto SaaS inicial para Perú: **AEOS Starter**, con autonomía supervisada. No construir tres planes comerciales ni billing recurrente en el MVP.

**Fuente de verdad del nuevo producto:**
- [Índice de control Starter](../starter/README.md)
- [Plan de MVP y arquitectura](../starter/AEOS_STARTER_MVP_PLAN.md)
- [Roadmap de 24 hitos](../starter/ROADMAP.md)
- [Registro de decisiones](../starter/DECISION_LOG.md)
- [Test ledger](../starter/TEST_LEDGER.md)
- [Checklist de release](../starter/RELEASE_CHECKLIST.md)
- [Issue principal #49](https://github.com/Franchute10/autonomous-agent-economy/issues/49)
- [PR de planificación #50](https://github.com/Franchute10/autonomous-agent-economy/pull/50), integrado en main mediante commit `db041a62b5dd84543695e8f953d1b254c42c299e`.

**Estado vigente (2026-11-25, S0-04):** PR #52 (draft, stacked on #51). Cloudflare Python Worker deployed in bootstrap build 9d98f04b-eb5e-48c7-9a2f-78e01cb7c54c (4 tests passed). Auth module and tests committed; GET /api/v1/me wired at 3698fb49026700bc9a085a28ea628afd2be9c50f. Supabase URL and publishable key configured as Worker bindings (no admin key). Auth build 17123a5b-06b8-4d05-a03f-7b3e9f7adaf4 initiated and running at last check. Verify final build, logs and live HTTP before claiming authentication works. Next: positive login and negative token checks, then organization onboarding using canonical Core schema/migrations and membership RLS. USD 0; protect Lumen and ferreteria domain. No AI inference or external actions yet.

**Siguiente acción:** verificar build de autenticación 17123a5b, probar /health y /api/v1/me; después implementar onboarding de organizaciones con aislamiento RLS real. Ver PR #52 y #51. No modificar otros proyectos.

**Regla de prioridad:** AEOS Starter es ahora el trabajo de producto activo. La antigua línea AEOS LIVE / diagnóstico web / leads de EE. UU. queda preservada como experimento separado y PAUSADA respecto al Starter; no mezclar sus objetivos, empresas piloto, fuentes, métricas o pagos con el mercado peruano de Starter.

## Retomar
1. Leer [el índice Starter](../starter/README.md) y [el roadmap](../starter/ROADMAP.md).
2. Verificar issues, ramas y SHAs actuales; leer AGENTS.md y el plan de Starter antes de editar.
3. Ejecutar la siguiente tarjeta habilitada. No solicitar nuevamente los chats ni repetir el ordenamiento general.
4. Registrar el resultado en GitHub al completar o bloquear cada tarea.

Este handoff gobierna la siguiente acción. Los apartados históricos posteriores preservan el piloto LIVE anterior y no sustituyen la prioridad Starter vigente.

Actualizado: 2026-11-21 (America/Lima). Planificación y ejecución focal; continuar con el modelo disponible.

## Retomar
1. Leer este archivo y [el plan ejecutable](LUNA_EXECUTION_PLAN.md).
2. Verificar issues, ramas y SHAs actuales; leer AGENTS.md y PROJECT_HANDBOOK.md antes de editar.
3. Ejecutar la siguiente tarjeta habilitada. No solicitar nuevamente los chats ni repetir el ordenamiento general.
4. Registrar el resultado en GitHub al completar o bloquear cada tarea.

Este archivo gobierna la siguiente acción; [PROJECT_CONTROL.md](PROJECT_CONTROL.md) fija el alcance. Handbook, readiness y ofertas anteriores conservan historia: sus estados fechados no sustituyen este corte. Las decisiones arquitectónicas aceptadas siguen vigentes.

## Objetivo y límites
URL o Google Business de un negocio de productos o servicios → diagnóstico gratuito con evidencia y prompt de corrección → oportunidades comerciales útiles, disponibles antes de ofrecer su compra.
USD 5 por 2–3 oportunidades y USD 10 por 5–6 son hipótesis. No restringir a limpieza ni a compras del Estado, ni prometer cobertura universal. Presupuesto incremental: USD 0. Sin contacto automático ni pagos reales.
AEOS conserva su propósito de organización gobernada de agentes; ampliar el runtime no es requisito previo para validar esta oferta. Fix Pack es un experimento separado.

## Piloto inicial — Estados Unidos
Empresas objetivo: **Construction Nation Group** (el propietario la refiere como “Nation Construction” y Dallas; el sitio existente es https://constructionnationgroup.com/ y habla de DFW/Plano) y **CMIMBELA Cleaning LLC** (el dictado reciente dice “Seminvela”; el historial y sitio usan https://cmimbelacleaningllc.com/, Sarasota). Mantener las grafías del sitio/registros y marcar las discrepancias de nombre; confirmar antes de cualquier material externo. Explorar solicitudes/clientes en Estados Unidos que encajen con la oferta realmente publicada o confirmada por cada empresa. No usar Mega Cerámicos, Lumen o AC Moreno como perfiles de esta validación, ni fuentes de compras públicas peruanas. LinkedIn sigue sin decidirse; no es fuente aprobada ni integración de este bloque. Presupuesto incremental USD 0; sin contacto automático.

## Estado verificado
| Entrega | Evidencia | Alcance real |
|---|---|---|
| Control y continuidad en main | PR #40 merge 963491a9; PR #41 merge 87055066; actualización documental PR #43 | Main conserva la dirección; LIVE sigue separada |
| Selector multisector | PR #39, merge f5cf0c64 | Rutas de productos, catálogos y servicios |
| Perfiles y ajuste de productos | PR #42, merge 548ed0c2; CI 949 passed / 12 skipped | Catálogo sin servicios y ajuste por products; no todos los formularios |
| Smoke técnico histórico (fuera del piloto actual) | Runs 44955224788 y 44955755471 | Mega Cerámicos y Lumen: 3 páginas; no valida Construction Nation ni CMIMBELA ni cuenta en métricas de ese piloto |
| Muestreo y prompt corregidos | PR #45, merge de2d211bc22cbbbe72b615e7434e649feca1b730; CI 44955889071: 953 passed / 12 skipped; lint/formato/mypy PASS | Rutas distintas antes de variantes; comparar contenido antes de cambiar metadatos |
| Google Business | Prueba local con entrada sintética | OWNER_EVIDENCE_REQUIRED, 0 páginas; no inspección real ni ingesta implementada |
| Exploración histórica fuera del piloto de EE. UU. | [Bitácora](ASTRA_EXECUTION_2026-11-21.md), ASTRA-SOURCE-001 | Muestra de compras públicas peruanas; no cuenta en resultados, denominadores ni decisiones del piloto actual |

LIVE verificada: `codex/aeos-live-003c` en `de2d211bc22cbbbe72b615e7434e649feca1b730`. Resolver SHA actual antes de editar.
Los resultados de Mega Cerámicos/Lumen son únicamente pruebas técnicas de los sitios de esas empresas; quedan fuera del piloto AEOS de EE. UU. No se certifica SEO completo, DOM, UI, conversión ni rentabilidad.
PR #44 está cerrado sin merge, como experimento completado y reemplazado por #45. La primera CI de #45 falló por formato del fixture; el head final pasó. No usar el fallo antiguo como bloqueo vigente.
La prueba real usa runner estándar del repo público, URLs fijas, sin secretos/API pagada/contacto ni cron. El entorno local sigue con limitaciones DNS/dependencias; no volver a declararlo bloqueo global.

## Pendientes preservados
- Revisión de 34 diferencias completada; no reaplicar parches. Reconciliación de laptop aún en [AEOS #4](https://github.com/Franchute10/autonomous-agent-economy/issues/4); no reset/clean ni staging masivo.
- Motor: PR #1 hacia main y PR #2 sobre la rama del #1 siguen como pila abierta en el último corte; verificar antes de editar. La base de evaluación documentada es a647263bcde2be074479321928b0cd74fc1c0252.
- No hay generación repetible de oportunidades útiles, venta de leads ni entrega comercial completa demostradas.
- AEOS PR #1/#2 de pagos requieren revisión separada. Entrega futura debe recuperar el resultado comprado inmutable; no rediagnosticar para reconstruirlo.
- Las pruebas reales y fuentes públicas están resumidas en la bitácora. Datos privados de prospectos, credenciales y journals no van al repo público.

## Corrección de alcance — 2026-11-21
La selección anterior de Mega Cerámicos, AC Moreno y Lumen, así como las muestras ASTRA-SOURCE-001/002 en SUTRAN, GOREMAD, DRTC, OECE/SEACE, fue una desviación del piloto solicitado. Se conserva como antecedente de un experimento peruano independiente; sus perfiles, resultados, ceros y denominadores no cuentan para validar AEOS en EE. UU. El smoke reciente de sitios Mega Cerámicos/Lumen tampoco cuenta como diagnóstico de los dos perfiles piloto. El historial anterior sí incluye inspecciones de los sitios de Construction Nation Group y CMIMBELA, pero deben distinguirse por fecha y versión; no atribuirles cobertura del código actual sin comparar la ejecución.

## Siguiente acción única — LUNA-002 / LEADS-VAL-001
Registro: [commercial-lead-engine #4](https://github.com/Franchute10/commercial-lead-engine/issues/4).
**Objetivo:** identificar una fuente permitida que entregue solicitudes pertinentes por perfil, antes de integrar una API o empaquetar datos.

Estado 2026-11-21: los comentarios previos de ASTRA-SOURCE-002 documentan una muestra de Perú fuera del alcance del piloto y no se usan como evidencia de yield. Workana continúa excluida de extracción/reventa sin permiso escrito, pero no es el canal elegido para los negocios objetivo.

1. Fijar perfiles con evidencia existente: Construction Nation Group (sitio en DFW/Plano; el propietario lo llama Dallas/Nation Construction) y CMIMBELA Cleaning LLC (Sarasota; “Seminvela” parece dictado). No inferir capacidad, disponibilidad, licencia, seguros, referencias ni submercados no confirmados.
2. Buscar únicamente oportunidades/clientes en Estados Unidos y separadamente por empresa, usando ofertas y geografía confirmadas por sus sitios o el dueño. Buscar primero fuentes públicas de necesidades explícitas con acceso permitido y coste incremental USD 0. Mantener prospectos B2B/partners como una categoría distinta de solicitudes de compra.
3. LinkedIn está en consideración, no aprobado: no conectar, automatizar ni contar resultados de LinkedIn hasta decisión expresa del propietario. No usar fuentes de Perú/OECE/SEACE para esta validación.
4. Congelar fuente, consultas, territorio estadounidense, ventana de fechas, límites y exclusiones. Abrir la fuente original y verificar necesidad, fecha/estado, ajuste, cobertura y vía legítima de respuesta. Excluir empleo, competidores/directorios sin intención, publicaciones vencidas y señales no accesibles.
5. Si no se acredita uso permitido y USD 0, no automatizar ni sortear controles. Registrar bloqueo y continuar solo con exploración manual permitida.
6. Etiquetar candidatos y una muestra de descartes; registrar denominadores por perfil, fuente y fecha. Mantener los prospectos individuales fuera del repositorio público. No presentar la muestra del negocio equivocado como evidencia.
7. Presentar al dueño solamente candidatos elegibles en una muestra privada para juzgar utilidad; no habilitar compra, precio ni entrega sin utilidad confirmada.
8. Registrar resultado y decisión en Motor #4, bitácora y este handoff. Después de tres corridas comparables sin utilidad, cambiar una hipótesis de fuente/canal/segmento; no inferir ausencia de mercado.


LUNA-003/004/005 siguen condicionadas a utilidad demostrada. LUNA-001 no necesita repetirse por cambiar de chat o modelo. No abrir otra ronda general de documentación.

## Continuidad obligatoria
Cada bloque deja ID/estado, fecha, repo/rama/base/head, PR, pruebas y denominadores, evidencia real o sintética, límites, decisión y siguiente acción.
Para un nuevo chat basta: “Continúa AEOS desde docs/control/NEXT_SESSION_HANDOFF.md en Franchute10/autonomous-agent-economy; verifica GitHub y ejecuta la siguiente tarjeta con presupuesto incremental USD 0”.


## Actualización S0-03 — 2026-11-25
2026-11-25: owner explicitly authorized isolated Supabase aeos-starter in São Paulo at USD 0/month, no upgrades or additional charges. Quote rechecked at USD 0; project created, ACTIVE_HEALTHY verified independently. Management SQL SELECT 1 returned connectivity=1, PostgreSQL 17.12, database postgres. Security advisor returned zero lints on empty project. No application schema, auth flow, Cloudflare connection, or RLS tested yet. Other projects untouched.


## 2026-11-25 — RLS y primera interfaz estática

2026-11-25: private PostgreSQL RLS spike migration applied only in dedicated aeos-starter project (source commit 77d155925f8e4121d637080a9af02fcb130a29a7, test 5800a7ad117856a14a44ab79c846353707918851). Test with SET LOCAL ROLE authenticated and synthetic JWT sub claims: 7/7 PASS (A own and cross-tenant, write privileges denied, B own and cross-tenant, unknown subject, anonymous grants). Transaction rolled back; 0 rows persisted; RLS enabled and forced; security advisor 0 lints. This is a private probe using owner identity, not production organization membership or Auth JWT verification. Cloudflare subscriptions GET denied HTTP 403 (missing billing:read); account entitlements did not establish Workers plan. Do not deploy metered Workers or invoke AI until free entitlement is verified. To deliver an early visual checkpoint, isolated Cloudflare Pages static-only project aeos-starter-preview created from the GitHub branch, build root spikes/starter_s0_03/preview, automatic production and preview deploys disabled. Manual deployment 264d0cc8-5c6d-4e6e-8e4f-bf98ccac6106 at SHA 2373804b0882963d0c456f590c316474a45d5893: all five Cloudflare stages succeeded. Deployment URL https://264d0cc8.aeos-starter-preview.pages.dev; independent HTTP check blocked by DNS in local execution and web tool could not access URL. Static asset requests free under both plans (https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/); no Pages Functions, paid services, billing upgrades, database credentials, model calls, or customer data. Preview is not a functioning SaaS or API. No other projects touched. Next: validate URL in browser, verify Workers free entitlement through dashboard or Billing Read, then isolated Python runtime deployment and DB connectivity; no metered operation before verified zero-cost path.
