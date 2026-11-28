## Continuidad después de abrir el PR — 2026-11-27 (America/Lima)

- Issue #53 está propuesta en [PR #54](https://github.com/Franchute10/autonomous-agent-economy/pull/54), rama `docs/aeos-arch-001-agent-quality-security-20261128`, contra `main` en `4a6979c5d1e15eba22df246b8d5c0c4a8d5deb53`.
- Head antes de este refresh: `ce078157db6b4a40d3cfcde54e1c4066718432a2`; push CI [46099493372](https://github.com/Franchute10/autonomous-agent-economy/actions/runs/46099493372) y PR CI [46099497267](https://github.com/Franchute10/autonomous-agent-economy/actions/runs/46099497267) — PASS.
- En ambos: Ruff, formato, mypy, 595 pruebas aprobadas, 7 omitidas, 8 pruebas Worker aprobadas y empaquetado — PASS. Comprobación manual de enlaces relativos: 0 rotos en 9 archivos modificados.
- El PR es documental: no implementa runtime, evaluación, memoria ni enforcement; auth válida, tenant authorization, PostgreSQL desde Worker y workflow Comercial E2E siguen sin verificarse.
- Este refresh crea un nuevo head; consultar SHA y CI actuales en GitHub antes de reutilizar el handoff. Mantener gasto incremental en USD 0.

Activador: `continua con lo trabajado en el chat: Agentes Mype`.

## Actualización operativa vigente — 2026-11-27 (America/Lima)

Esta sección prevalece sobre los snapshots históricos que describen los PR #51/#52 como abiertos o el Worker como staged.

### Main, PRs y CI
- PR #51 merged: `08ad7dd6fe98123cad89a1acc5000b7310e2e9b5`.
- PR #52 merged: `4a6979c5d1e15eba22df246b8d5c0c4a8d5deb53`, ahora head de `main). Push CI de main [46098462896](https://github.com/Franchute10/autonomous-agent-economy/actions/runs/46098462896) — PASS.
- Issue #53 está en ejecución desde `docs/aeos-arch-001-agent-quality-security-20261128`, creada desde main SHA `4a6979c5d1e15eba22df246b8d5c0c4a8d5deb53`. Registrar y consultar el head exacto luego de cada commit. No abrir otra rama técnica en paralelo.

### Estado del producto y límites
- AEOS Core es el kernel organizacional/económico; AEOS Starter es el producto SaaS inicial para Perú, con autonomía supervisada y Comercial como único departamento con workflow completo previsto en v0.1; Agentes Mype es la capa de aplicación, no un runtime paralelo.
- Workers Free está confirmado por el propietario; gasto incremental autorizado: USD 0. No contratar planes ni usar inferencia pagada.
- Worker existente v6 al 100%; smoke: health 200, capabilities 200, /me sin token 401. Esto no verifica sesión Supabase válida, membership/permiso multi-tenant, ni conexión PostgreSQL desde el Worker. No declarar autenticación real ni workflow end-to-end listos.
- No se enviaron credenciales ni datos de clientes. Modelo y ejecución de agentes siguen deshabilitados.

### Trabajo en curso: Issue #53
- Preparar y enlazar estándar de calidad, contrato de agente/skill, formato de evaluación determinista y matriz de seguridad, revisados frente a ADR-001–008 y al código.
- Mantenerlos como especificaciones, no como funciones implementadas.
- Tras cambios, consultar el SHA actual de la rama y CI; crear el PR de scope documental con evidencias y límites.
- Issue #53 no puede marcarse DONE por documentos solamente si la aceptación exige controles ejecutables; reportar con precisión cualquier límite.

Activador de continuidad: `continua con lo trabajado en el chat: Agentes Mype`.

# AEOS — Continuidad vigente
Actualizado: 2026-11-27 (America/Lima). **Prioridad vigente: AEOS Starter MVP**.

## Actualización vigente — 2026-11-27 (America/Lima)

Esta sección es el estado más reciente y prevalece sobre las secciones históricas más abajo que aún describen el Worker como staged o la URL de Pages como no verificada.

### PRs y CI
- PR #51: **merged** a `main` mediante merge commit `08ad7dd6fe98123cad89a1acc5000b7310e2e9b5`; CI anterior a la integración: run [46092750914](https://github.com/Franchute10/autonomous-agent-economy/actions/runs/46092750914) — PASS.
- PR #52: abierto, Draft, sin revisiones; ahora apunta directamente a `main` en `08ad7dd6fe98123cad89a1acc5000b7310e2e9b5`. Head antes de esta actualización: `18d51c5bfc0470ff9a94d63042b1483f86b5bb5f`; CI run [46092875990](https://github.com/Franchute10/autonomous-agent-economy/actions/runs/46092875990) — PASS cuando aún estaba apilado sobre la rama de #51. Verificar CI tras el cambio de base y este commit.
- Issue #53 sigue QUEUED/BLOCKED por PR #52. No abrir otra rama activa hasta resolverlo.

### Evidencia HTTP actual
- Pages estático `aeos-starter-preview`: GET público el 2026-11-27 devolvió HTTP 200. El HTML incluye `noindex,nofollow` y explica que no autentica ni ejecuta tareas.
- Worker existente `aeos-starter-api`: versión 6 `4bd80ea2-7f08-4440-b8d0-62daeb2c6cdf` desplegada al 100% en deployment `de125f5c-7da1-43b1-bab9-6ad889412fa6`.
- Smoke checks antes y después del despliegue: `/health` 200, `/api/v1/capabilities` 200, `/api/v1/me` sin token 401. No se enviaron tokens ni datos de clientes.
- `/health` aún informa `authentication_live_verified: false`. El 401 solo comprueba rechazo de token ausente; no demuestra sesión Supabase válida, membership, autorización multi-tenant, ni conexión PostgreSQL.
- Capabilities informa `side_effects: false` y `customer_data_enabled: false`; inferencia de modelos y ejecución de agentes siguen deshabilitadas. No se modificaron plan, DNS, Workers ni secretos; se mantuvo Workers Free y gasto incremental autorizado USD 0.

### Próxima acción
Revisión y resolución humana de PR #51; después revisar/resolver PR #52 ya contra la base actualizada. Cuando ambos queden resueltos, volver a consultar main, ramas, heads y CI; recién entonces ejecutar Issue #53 desde una rama limpia basada en main vigente. No afirmar que el producto SaaS, la autenticación real o un workflow Comercial end-to-end estén implementados.

Activador de continuidad solicitado por el propietario: `continua con lo trabajado en el chat: Agentes Mype`.


## Prioridad y separación de producto

- **AEOS Core:** kernel organizacional/económico para organizaciones de agentes: organización, roles, autoridad, gobernanza, economía, workflows, runtime, evidencia, auditoría y aprendizaje. La tesis es construir una organización gobernada, no un enjambre de prompts.
- **AEOS Starter:** primer producto SaaS funcional, mercado inicial Perú, autonomía supervisada. Comercial es el único departamento previsto con workflow completo end-to-end en v0.1; los demás se muestran como catálogo, sin simular que ya operan. No abrir Growth/Business ni billing recurrente en este MVP.
- **Agentes Mype:** visión/capa de aplicación de AEOS para que una MYPE opere con capacidades de una empresa mayor. No sustituye AEOS Core ni se convierte en runtime o producto paralelo que compita con Starter.
- **AEOS LIVE y Commercial Lead Engine:** líneas separadas; no mezclar sus pilotos, fuentes, empresas, métricas o código con Starter sin una tarea e interfaz aprobadas.

## Fuente de verdad y control

- [Índice Starter](../starter/README.md)
- [Plan Starter](../starter/AEOS_STARTER_MVP_PLAN.md)
- [Roadmap Starter](../starter/ROADMAP.md)
- [Decision log](../starter/DECISION_LOG.md)
- [Test ledger](../starter/TEST_LEDGER.md)
- [Project control](PROJECT_CONTROL.md)
- [Issue principal #49](https://github.com/Franchute10/autonomous-agent-economy/issues/49)
- [Issue AEOS-ARCH-001 #53 — integración selectiva ECC](https://github.com/Franchute10/autonomous-agent-economy/issues/53)

GitHub es la fuente de verdad. El chat ayuda a decidir y ejecutar, pero no sustituye issues, PR, commits, pruebas ni este handoff.

## Estado de GitHub verificado — 2026-11-27

Repositorio: `Franchute10/autonomous-agent-economy`; rama por defecto: `main`.

| Elemento | Base | Referencia comprobada | Estado |
|---|---|---|---|
| main | — | `1ef00bacd00a14d7e79a4f558c4fd2987307c9ee` | Rama canónica al momento de la consulta |
| [PR #51](https://github.com/Franchute10/autonomous-agent-economy/pull/51) | `main` | head registrado `bb3b469a4c42ac075b7e72e53de2bb5f9e246d6d` | Draft; S0-03; no integrado. Verificar checks vigentes |
| [PR #52](https://github.com/Franchute10/autonomous-agent-economy/pull/52) | `product/aeos-starter-s0-03-20261125` | SHA dinámico: consultar el head vivo de GitHub; último candidato de código probado `513b83167f0271514088bc20e44e8f43d4fbbbaf` | Draft; S0-04; no integrado |
| [Issue #53](https://github.com/Franchute10/autonomous-agent-economy/issues/53) | — | — | Abierta; QUEUED, bloqueada por #51/#52 |

### Validación de PR #52

El candidato de código `8f28d3836fde9354cd2eb79ae30286015f5d11e7` obtuvo:
- GitHub Actions CI push: run [46081019608](https://github.com/Franchute10/autonomous-agent-economy/actions/runs/46081019608) — PASS.
- GitHub Actions CI pull request: run [46081025651](https://github.com/Franchute10/autonomous-agent-economy/actions/runs/46081025651) — PASS.
- Ruff lint: PASS.
- Ruff format: PASS (204 archivos ya formateados).
- Mypy: PASS.
- Pytest: **595 passed, 7 skipped**.

Fallos previos del mismo PR, ya corregidos en el candidato validado:
- Run 46080525054: Ruff E402 por imports de tests fuera de cabecera.
- Run 46080659280: Ruff format en auth.py, worker.py y test_app.py.

El head documental `1011c59530050d1fea1a977c7fbe20d4957bb1d8` obtuvo push run [46082800734](https://github.com/Franchute10/autonomous-agent-economy/actions/runs/46082800734) y PR run [46082802373](https://github.com/Franchute10/autonomous-agent-economy/actions/runs/46082802373), ambos PASS. Después se añadió este checkpoint de handoff a la misma rama, lo que genera un nuevo head y una nueva ejecución CI. **El SHA exacto del head posterior a este documento debe consultarse en GitHub; no se auto-referencia el SHA de un archivo dentro del commit que lo crea.** El candidato de código probado actualizado es `513b83167f0271514088bc20e44e8f43d4fbbbaf`.

### CI y evidencia de infraestructura — 2026-11-27

**CI verificada:**
- PR #51, head `bb3b469a4c42ac075b7e72e53de2bb5f9e246d6d`: push run [45557284664](https://github.com/Franchute10/autonomous-agent-economy/actions/runs/45557284664) PASS; PR run [45554584495](https://github.com/Franchute10/autonomous-agent-economy/actions/runs/45554584495) PASS; push run [45554576178](https://github.com/Franchute10/autonomous-agent-economy/actions/runs/45554576178) PASS.
- PR #52, code + CI workflow head `ee1f2ccfe235df7e61c31b926cae063ec67d449c`: push run [46083894693](https://github.com/Franchute10/autonomous-agent-economy/actions/runs/46083894693) PASS; PR run [46083898722](https://github.com/Franchute10/autonomous-agent-economy/actions/runs/46083898722) PASS. Root suite: **595 passed / 7 skipped**; Worker adapter suite: **8 passed on Python 3.13**. The Worker-specific tests now run explicitly from `deploy/cloudflare/aeos-starter-api`; root `pytest` alone did not collect them. This handoff checkpoint itself is a later commit; verify the live branch head and its CI on the next resume.
- Código del PR #52 en `513b83167f0271514088bc20e44e8f43d4fbbbaf`: fail-closed auth distinguishes anonymous accounts (403) from malformed upstream user payloads (503); added tests for malformed headers/config, upstream 500, missing `is_anonymous`, invalid UUID and non-object payload. Ruff lint/format PASS, mypy PASS. En el head con CI ampliada `ee1f2ccfe235df7e61c31b926cae063ec67d449c`: root pytest **595 passed / 7 skipped** y Worker adapter pytest **8 passed** bajo Python 3.13.

**Supabase — verificación actual de solo lectura:**
- Organización Supabase: plan `free` (confirmado por Management API). Proyecto `aeos-starter`: ID `ltdarjzxdrwffilmsftm`, región São Paulo (`sa-east-1`), PostgreSQL 17.12, estado `ACTIVE_HEALTHY`.
- Una migración: `20261125053223_starter_s0_03_private_rls_probe`.
- Única tabla custom: `aeos_spike.tenant_probe`, en esquema privado. No hay tablas de negocio Starter.
- Security advisor: 0 lints; performance advisor: 0 lints.
- El probe RLS registrado fue **7/7 PASS** con identidades/datos sintéticos, writes denegados y rollback; no demuestra Auth real, membership ni autorización de tenants en la API.

**Cloudflare — verificación actual de solo lectura:**
- Pages `aeos-starter-preview`: deployment `264d0cc8-5c6d-4e6e-8e4f-bf98ccac6106`, SHA `2373804b0882963d0c456f590c316474a45d5893`, cinco etapas exitosas, `uses_functions=false`. URL: https://264d0cc8.aeos-starter-preview.pages.dev. No se pudo verificar su respuesta HTTP desde esta sesión.
- Worker `aeos-starter-api`: subdominio workers.dev `frank-2e`; deployment activo `fba5c2a4-4ef0-4685-8e77-0a396e487074`; versión activa `ec0cab99-437b-47da-bb66-bca749b95776` (version 5), creada/desplegada el 2026-11-25.
- **Hallazgo crítico:** el contenido descargado del Worker activo contiene el `app.py` bootstrap anterior. Su `/health` reporta `authentication_enabled: false`; `/api/v1/capabilities` no anuncia Auth; no contiene `worker.py`, `auth.py` ni la ruta `/api/v1/me` del código actual del PR #52. Por tanto, el código de PR #52 **no está desplegado**; la versión activa sigue siendo placeholder.
- La URL configurada del Worker es https://aeos-starter-api.frank-2e.workers.dev, pero no se pudo comprobar HTTP desde esta sesión.
- **El propietario confirmó con dos capturas del dashboard (2026-11-27) que la cuenta está en Workers Free:** la pestaña `Límites de gasto` muestra Workers y Durable Objects en `Nivel gratuito`; `Suscripciones` muestra `Workers Free — Activo`, ofrece `Actualizar a Workers Paid` por USD 5/mes más uso y no tiene método de pago registrado. No existe suscripción Paid ni gasto activo según el dashboard. La inferencia anterior basada en `usage_model: standard` fue incorrecta: ese campo de configuración/API no debe usarse por sí solo para inferir la suscripción de la cuenta. La evidencia del dashboard prevalece. Mantener el límite de gasto incremental USD 0 y no habilitar productos de pago.

### Intento de empaquetado Worker — 2026-11-27

- Se intentó crear una versión no desplegada vía Cloudflare Version Upload para el Worker existente, con `keep_bindings: ["secret_text"]` y sin leer ni sobrescribir secretos.
- La primera carga fue rechazada con error 10021: falta el módulo `workers` del SDK externo. La segunda, sin el vendor SDK, fue rechazada también con error 10021. **No se creó versión ni deployment; el Worker activo y sus secretos permanecen intactos.**
- La documentación y el repositorio oficial `cloudflare/workers-py` confirman que el SDK debe empaquetarse en `python_modules/` mediante `pywrangler sync`; la solución no es desactivar `python_workers` ni añadir el flag `disable_python_external_sdk`.
- Se elevó el mínimo de dependencias del proyecto a `workers-py>=1.17.9,<2` y `workers-runtime-sdk>=1.9.7,<2`.
- Se añadió a CI una etapa explícita que ejecuta `uv sync --all-groups`, `uv run pywrangler sync` y verifica `python_modules/workers/__init__.py` y `python_modules/_workers_sdk_patch_loader.pth`.
- Commit de dependencias: `7f13b3a89a6afb64bf3045255f01227640a310f1`; commit del workflow CI: `af99ae18de851a407d0a1d3184920b2a37004f8c`. CI push `46085765986` y PR `46085768182` estaban en ejecución al guardar este checkpoint. No declarar PASS hasta verificar ambos resultados.

### Worker versión 6 — SDK empaquetado y staged (2026-11-27)

- Se subió correctamente una versión no desplegada al Worker existente `aeos-starter-api`, usando el SDK oficial de `cloudflare/workers-py` (runtime-sdk 1.9.7) bajo `python_modules/`.
- Version ID: `4bd80ea2-7f08-4440-b8d0-62daeb2c6cdf`; número 6; `has_preview=true`; source `api`; handlers `fetch`.
- Código: `worker.py`, `app.py`, `auth.py`; SDK empaquetado con módulos `workers` y loader `.pth`. Se conservó `compatibility_date=2026-11-25` y flag `python_workers`.
- Se usó `keep_bindings: ["secret_text"]`. La respuesta de versión y la configuración actual confirman que siguen presentes las dos bindings `SUPABASE_URL` y `SUPABASE_PUBLISHABLE_KEY`; no se leyeron ni modificaron sus valores.
- URL de versión: https://4bd80ea2-aeos-starter-api.frank-2e.workers.dev
- La deployment activa sigue siendo `fba5c2a4-4ef0-4685-8e77-0a396e487074`, versión 5 `ec0cab99-437b-47da-bb66-bca749b95776`, al 100%. La versión 6 **no recibe tráfico de producción**.
- La prueba HTTP automatizada desde esta sesión no es posible: el acceso web no resuelve el hostname `workers.dev`, y los sandboxes de ejecución bloquean requests salientes a ese hostname. No inferir funcionamiento a partir de `has_preview=true` ni de una carga exitosa. El propietario debe abrir los tres endpoints read-only indicados en el chat; después se podrá desplegar al 100% si las respuestas son correctas.

### Límites de lo que está probado

La CI es local/sintética. No prueba despliegue del código actual de PR #52, HTTP reachability, login real, aceptación de token, conexión PostgreSQL desde Worker, membership/onboarding, RLS desde el runtime, Model Gateway, workflows durables ni ejecución de agentes. La versión desplegada de Cloudflare es un placeholder antiguo y no debe confundirse con el código de la rama. No leer ni copiar valores de secretos. El plan Free permite ejecutar el Worker dentro de los límites documentados: 100.000 requests/día, 10 ms CPU/request, 128 MB memoria y 50 subrequests/request; diseñar y probar dentro de esos límites.

## Siguiente secuencia técnica

1. Resolver la dependencia PR #51 → PR #52 mediante revisión humana. Ambos siguen Draft; no hacer merge automáticamente.
2. Verificar manualmente desde navegador la URL estática y el endpoint configurado del Worker. No enviar tokens ni datos sensibles en capturas.
3. El dashboard del propietario ya confirmó Workers Free y ausencia de método de pago. Python Workers es compatible con el runtime de Workers; respetar el límite Free de 100.000 requests/día y 10 ms CPU/request. No habilitar Workers AI, Durable Objects pagos, Containers, Hyperdrive ni servicios metered.
4. La versión 6 ya está cargada y staged. El propietario debe comprobar la URL de versión: `/health` 200, `/api/v1/capabilities` 200 y `/api/v1/me` sin token 401. No enviar token real. Si cualquiera falla, no desplegar; corregir código y volver a subir otra versión staged preservando `secret_text`.
5. Solo tras smoke tests aprobados, crear deployment con versión 6 al 100% del tráfico. Después repetir smoke tests en la URL estable y registrar status, payload sanitizado, SHA, version ID y deployment ID. No declarar Auth real antes de probar con un usuario sintético controlado si el propietario lo autoriza.
6. Probar conexión PostgreSQL desde el runtime y membership/RLS con dos tenants sintéticos; separar la prueba de identidad de la autorización organizacional.
7. Mantener AEOS-ARCH-001 (#53) en QUEUED mientras #51/#52 no estén resueltos. Después crear rama limpia desde el main vigente e implementar estándares ECC de calidad, seguridad, skills y evaluaciones deterministas.
8. Mantener gasto incremental USD 0. No upgrades, inferencia pagada ni servicios metered.

## Continuidad del chat — activador exacto

Cuando el propietario escriba:

`continua con lo trabajado en el chat: Agentes Mype`

retomar desde este handoff y desde el estado actual de GitHub. No reiniciar el proyecto, no pedir que vuelva a pegar conversaciones o decisiones ya registradas y no asumir que los SHAs de este documento siguen vigentes.

Procedimiento obligatorio al retomar:
1. Consultar GitHub: main, PR abiertos, issues activos, ramas, base/head SHA, checks/Actions y dependencias.
2. Leer `AGENTS.md`, `docs/PROJECT_READINESS.md`, `PROJECT_HANDBOOK.md`, `docs/control/PROJECT_CONTROL.md`, este handoff, Starter README/plan/roadmap/test ledger, ADR index y el issue/PR de la siguiente tarea.
3. Identificar la siguiente tarea no bloqueada y respetar el máximo de dos tareas técnicas activas.
4. Preservar las decisiones ya confirmadas; preguntar solo si falta una decisión realmente nueva o una autorización necesaria.
5. Ejecutar trabajo verificable, no limitarse a resumir ni a volver a planificar lo ya aprobado.
6. Cerrar cada bloque actualizando GitHub: issue, PR, rama, SHA, comandos, entorno, resultados con denominadores, evidencia real/sintética, fallos, riesgos, decisiones, estado y siguiente acción única.
7. Antes de cambiar de chat o terminar la sesión, actualizar este handoff con el nuevo estado verificado.

## Retomar
1. Leer [el índice Starter](../starter/README.md) y [el roadmap](../starter/ROADMAP.md).
2. Verificar issues, ramas y SHAs actuales; leer AGENTS.md y el plan de Starter antes de editar.
3. Ejecutar la siguiente tarjeta habilitada. No solicitar nuevamente los chats ni repetir el ordenamiento general.
4. Registrar el resultado en GitHub al completar o bloquear cada tarea.

Este handoff gobierna la siguiente acción. Los apartados históricos posteriores preservan el piloto LIVE anterior y no sustituyen la prioridad Starter vigente.

Actualizado: 2026-11-27 (America/Lima). Planificación y ejecución focal; continuar con el modelo disponible.

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
