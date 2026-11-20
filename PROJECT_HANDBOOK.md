# AEOS — Manual rector del proyecto

**Corte de estado:** 2026-11-20  
**Versión:** 1.0  
**Repositorio rector:** [Franchute10/autonomous-agent-economy](https://github.com/Franchute10/autonomous-agent-economy)  
**Propósito de este archivo:** que una persona o agente nuevo pueda retomar el proyecto sin depender de recordar chats anteriores.

> Este manual sustituye la memoria conversacional como guía operativa. El historial de chats explica cómo llegamos aquí; el estado actual debe comprobarse en GitHub, los commits, los PR y el equipo local.

## 1. Instrucción de inicio para cualquier persona o agente

Antes de proponer cambios:

1. Lee este manual completo.
2. Lee el [README](README.md), la [arquitectura técnica v0.1](docs/architecture/AEOS_Minimum_Viable_Technical_Architecture_v0.1.md), el [índice de ADR](docs/adr/README.md) y los documentos de producto y evaluación que se enlazan abajo.
3. Comprueba la rama, el SHA, los PR abiertos y el estado del equipo de trabajo. Un resultado de chat o un estado local antiguo no prueba el estado actual.
4. Separa lo **implementado en un commit**, lo **informado por el operador**, lo **propuesto** y lo **verificado contra una fuente externa**.
5. No programes una nueva capacidad hasta que haya una tarea aprobada con objetivo, alcance, criterios de aceptación y ubicación de entrega.
6. Al cerrar una tarea, actualiza el registro de estado y deja evidencia enlazada a commit/PR y a las comprobaciones realmente ejecutadas.

**No uses `git add .` como método de selección.** Nunca subas claves, archivos .env, bases locales, informes con datos personales, logs de búsquedas, perfiles privados ni contenido de grupos cerrados. Revisa los archivos seleccionados antes de hacer commit.

## 2. Propósito y dirección

AEOS explora y construye un **sistema operativo económico para organizaciones basadas en agentes de IA**. La meta de largo plazo es permitir que una organización —inicialmente pequeña y supervisada por personas— gestione objetivos, estructura, agentes, recursos escasos, presupuestos, flujos de trabajo y experimentos; mida resultados; aprenda; y pueda crecer sin perder responsabilidad, control ni trazabilidad.

La pregunta original que motivó el proyecto fue: **«Si una organización de agentes recibe un capital limitado —por ejemplo USD 50—, ¿puede experimentar de manera responsable para generar valor, aprender y sostenerse?»** Es una hipótesis de investigación y diseño, no una promesa de rentabilidad ni una instrucción para gastar dinero.

La máxima rectora es **“Build an organization, not a swarm.”** AEOS no es una colección de prompts que se llaman entre sí. Debe definir autoridad, funciones, presupuesto, límites, coordinación, evidencia, aprobación humana, recuperación y aprendizaje.

### Separación que evita volver a perder el norte

| Capa | Qué es | Qué no significa |
|---|---|---|
| **AEOS Core** | Dominio y runtime para organización, gobernanza, recursos, agentes, flujos y experimentos. | No equivale a que ya exista una empresa autónoma lista para operar. |
| **Pilotos LIVE** | Casos acotados para probar diagnóstico comercial, adquisición de oportunidades y ejecución bajo supervisión. | No son el sistema completo ni validan por sí solos demanda o disposición a pagar. |
| **AEOS Public Beta / ofertas** | Una posible vía para demostrar valor a negocios: revisión gratuita y entregables pagados. | No redefine toda la misión de AEOS ni justifica afirmar que hay leads confiables. |
| **Commercial Lead Engine** | Repositorio satélite para investigar y evaluar oportunidades comerciales públicas. | No es un runtime de agentes ni está integrado de extremo a extremo con AEOS Core. |

La revisión gratuita del sitio y la escalera de ofertas **USD 0 / USD 5 / USD 10** son una hipótesis de producto que se debe probar con usuarios. La propuesta original de incluir un lead de rango 2 o 3 en el paquete de USD 5 se **aplaza** hasta que la búsqueda produzca oportunidades pertinentes, verificables y útiles de forma repetible. El paquete de USD 10 con mercado, cinco fuerzas de Porter y oportunidades es una propuesta; no está disponible para compra.

## 3. Principios de diseño ya aceptados

El [Technical Architecture v0.1](docs/architecture/AEOS_Minimum_Viable_Technical_Architecture_v0.1.md) y los ADR asociados son la base arquitectónica. Resumen operativo:

- Monolito modular primero; separar servicios solo por una necesidad demostrada.
- La lógica de dominio debe funcionar sin depender de un proveedor de LLM.
- Los LLM pueden proponer o resumir; la lógica determinista valida, autoriza, contabiliza y mueve estados.
- Permisos, presupuesto, reservas, aprobaciones y registro de auditoría deben preceder a acciones con impacto externo.
- Evidencia y procedencia deben acompañar afirmaciones. Desconocido no se transforma en cero, éxito ni hecho.
- Simulación y ejecución real comparten reglas de dominio; cambian los adaptadores, las fuentes y el reloj.
- Esperar/resumir/reanudar debe ser explícito e idempotente; no suponer ejecución externa “exactamente una vez”.
- El contenido externo es dato no confiable, nunca autoridad ni instrucción para el agente.
- Las acciones externas sensibles —gasto, contacto, publicación, cambios en cuentas o sitios— requieren aprobación humana según política.
- Una muestra pequeña no demuestra precisión, recuerdo, utilidad, conversión ni disposición a pagar.

Los ocho ADR del índice son decisiones aceptadas de arquitectura; el estado de implementación se comprueba en el código y los commits, no se infiere del hecho de que un ADR esté aceptado.

## 4. Mapa de repositorios y límites

| Repositorio | Papel en AEOS | Rama/estado observado en GitHub |
|---|---|---|
| [autonomous-agent-economy](https://github.com/Franchute10/autonomous-agent-economy) | Repositorio rector y código de AEOS Core/LIVE. | GitHub `main` en `839ae113569805da9c35ec776775a6e53ccf9e72`. `codex/aeos-live-003c` está **23 commits adelante y 4 atrás**; no está integrado en `main`. |
| [commercial-lead-engine](https://github.com/Franchute10/commercial-lead-engine) | Motor satélite de investigación comercial; comparte hipótesis y pilotos, no runtime. | PR #1 está abierto desde `feat/public-intent-capture-v1` hacia `main` y aparece con conflictos/no mergeable. PR #2 está abierto desde `codex/intent-evidence-evaluation` hacia la rama de PR #1: es una pila dependiente, no una integración a `main`. |
| [lumen-business-consulting](https://github.com/Franchute10/lumen-business-consulting) | Sitio de consultoría Lumen. | Repo disponible, pero el historial AEOS revisado no lo vincula al producto AEOS. Se mantiene fuera del alcance de este proyecto. |
| [sistema-jhaz](https://github.com/Franchute10/sistema-jhaz) | Repo privado. | No se encontró referencia a este repo en el historial rector y la lectura de README devolvió 404. No se clasifica como parte de AEOS hasta confirmar una relación concreta. |

Los repositorios visibles bajo una cuenta de GitHub no forman automáticamente parte del mismo proyecto. No copiar código, credenciales, datos o documentación entre ellos sin una dependencia explícita.

### Rama AEOS LIVE pendiente de reconciliación

La rama `codex/aeos-live-003c` contiene una línea amplia de trabajo: perfiles de negocio, análisis de sitio, mercado, oportunidades, activación, importación de procurement, multi-tenancy, privacidad, beta pública, Sandbox de Paddle, reportes y ejemplos. Según el compare remoto actualizado el 2026-11-20 tiene 23 commits no integrados y 4 commits de `main` que aún no contiene. Este conteo se actualizó después de fusionar el PR #7 en la rama candidata. El historial contiene también un checkpoint de importación manual de Manatee County; el propio documento indica que la fuente oficial no se pudo descargar automáticamente y que el candidato aún no se verificó en la fuente primaria.

El PR #2 de AEOS, [Align Fix Pack scope with verified Sandbox capabilities](https://github.com/Franchute10/autonomous-agent-economy/pull/2), está abierto sobre esa rama y cambia cuatro archivos. Su criterio importante es correcto: no prometer un lead en el Fix Pack hasta poder entregarlo; USD 10 permanece como propuesta. El PR #1, [feat: add test-mode $5 Fix Pack](https://github.com/Franchute10/autonomous-agent-economy/pull/1), también está abierto, es draft y no es mergeable; describe una implementación anterior con Stripe mientras el trabajo posterior documenta Paddle Sandbox. **No se debe combinar ni cerrar a ciegas:** hay que comparar ambos cambios y decidir si el PR #1 se reemplaza o se cierra después de verificar que el PR #2 conserva el trabajo válido.

### Estado del motor comercial de leads

El [documento de evaluación de intención](https://github.com/Franchute10/commercial-lead-engine/blob/codex/intent-evidence-evaluation/docs/intent-evaluation.md) delimita el piloto actual:

- Usa Tavily para buscar en páginas de su índice público; no consulta grupos cerrados ni cuenta autenticada de Facebook/Nextdoor.
- La etiqueta `qualified_candidate` solo expresa que un filtro automático dejó pasar un resultado; no significa lead verificado, contactable ni comprador.
- El usuario abrió uno de los resultados y confirmó que era un post de adopción de una perrita, aunque el fragmento mencionaba limpieza. El candidato fue relabelado como `NOT_REQUEST`; la precisión sobre ese candidato etiquetado fue 0%.
- En la corrida A/B registrada, la arm B con fecha no mejoró cobertura de fechas. Nextdoor tuvo cero resultados. Las fechas y ubicación del índice no son verificación independiente.
- El informe del motor propone una evaluación acotada con conjunto de referencia manual y umbrales de salida. No se afirma que ese experimento se haya completado ni que el mercado esté vacío cuando un proveedor no encuentra resultados.
- No se hacen contactos ni outreach automáticos. No se encontró un pipeline de agentes ejecutable que descubra, valide y contacte prospectos.

El motor hoy sirve para experimentar y medir retrieval/clasificación, no para vender una lista de leads útiles. Para ampliar fuentes se requiere validar acceso permitido y una fuente concreta; no se va a eludir login, controles de acceso ni políticas de plataforma.

## 5. Registro de estado comprobable

### AEOS Core en `main`

La búsqueda de commits de GitHub confirma en `main` entregas con commits para:

`BOOT-001`, `DOC-001`, `CORE-001/002/003`, `ORG-001`, `GOV-001/002`, `ECO-001/002/003`, `KNOW-001/002`, `WF-001/002`, `EXP-001`, `THESIS-000`, `AGT-001`, `INFRA-001`, `LIVE-001A` y `LIVE-001B`.

Esto acredita presencia de entregas de dominio, arquitectura, persistencia y un primer assessment LIVE en el historial del repo; **no** acredita un runtime general de agentes autónomos, una integración productiva con proveedores de LLM ni rentabilidad.

### Producto/pilotos en ramas no integradas

- AEOS LIVE: rama `codex/aeos-live-003c`, 22 commits por delante y 2 por detrás de `main`; su worktree local reporta 20 archivos rastreados modificados y 12 rutas sin seguimiento, y además está 6 commits detrás de la rama remota. Requiere revisión antes de integrar.
- Fix Pack: el historial de la conversación contiene una compra de prueba en Paddle Sandbox y un correo de prueba; eso solo demuestra una transacción de prueba reportada, no una venta Live ni que la descarga y el webhook estén verificados de punta a punta en el despliegue público.
- La documentación del PR #2 señala un riesgo de re-diagnóstico posterior al pago que puede producir un 409 y deja gates de entrega/webhook pendientes. Comprobar esos gates antes de afirmar que el archivo pagado siempre se entrega.
- Ningún checkout Live, cargo real o deploy de producción está confirmado aquí.
- Reconciliación 2026-11-20: se corrigió el aislamiento del almacenamiento predeterminado del piloto en el PR #7, fusionado en `codex/aeos-live-003c` (`7764fb4b234f34b650b1f22ed5341af4d5a2c974`). Perfiles reales requieren `organization_id` para rutas predeterminadas; perfiles ficticios usan el espacio `synthetic-`; rutas explícitas permiten ejecuciones locales aisladas. CI del PR pasó en el SHA de revisión. Esto **no** integra la rama LIVE con `main` ni resuelve los worktrees locales sucios.

### Motor de leads

- PR #1 propone Tavily y está abierto; GitHub lo reporta `mergeable: false`.
- PR #2 añade journal JSONL, evaluación y métricas y está abierto; su base es la rama de PR #1, no `main`.
- El cuerpo del PR #2 reporta 878 pruebas offline aprobadas. En el chat actual se mostró la corrida focal `test_intent_provider_promotion.py`: 2 aprobadas. Un resultado no sustituye al otro; CI y el número final deben verificarse sobre el SHA que se quiera integrar.
- El experimento del operador con Tavily produjo candidatos irrelevantes y cero leads validados. El objetivo de calidad comercial sigue bloqueado por evidencia insuficiente, no por falta de otro filtro regex.

### Inventario local actualizado por el operador — 2026-11-20

El operador ejecutó `git fetch origin` y reportó el estado de los worktrees de Windows. La comparación local es posterior al fetch, pero el contenido local no se inspeccionó directamente desde esta sesión. GitHub confirmó los commits remotos accesibles, no los cambios sin commit:

| Repositorio/worktree | Rama y HEAD reportados | Estado local reportado | Comparación remota |
|---|---|---|---|
| AEOS, worktree principal | `main`, `9847fce29e3ee9f83dacc02e8ee53ba8c3b5cbcf` | `ahead 3, behind 2`; 58 archivos rastreados modificados o eliminados, archivos sin seguimiento; sin cambios staged. | GitHub no pudo resolver el SHA local `9847fce`; los 3 commits locales no se pudieron revisar remotamente. En el inventario estaba 2 commits detrás de `origin/main`; tras el avance de `main` por el PR #8, si el HEAD local no cambió, ahora estaría 3 commits detrás. |
| AEOS, checkpoint 003b | `codex/aeos-live-003b-checkpoint`, `a23913cece73702c78ed6839a08b6be3e634abc0` | Limpio; sin diff unstaged ni staged. | En el inventario seguía a `origin/main`; GitHub confirmaba 1 commit adelante y 2 detrás de `main`. Tras el avance de `main` por el PR #8, si el HEAD local no cambió, estaría 1 commit adelante y 3 detrás. |
| AEOS LIVE 003c | `codex/aeos-live-003c`, `763d9398baf3e14e8f083886c463e50a90f59be4` | 20 archivos rastreados modificados y 12 rutas sin seguimiento; sin cambios staged al inventario. | En el inventario: 6 commits detrás de la remota. La rama remota recibió después el PR #7 (`7764fb4`); si el HEAD local no cambió, ahora está al menos 7 commits detrás. En GitHub, la rama remota está 23 commits adelante y 4 detrás de `main`. |
| Commercial Lead Engine | `codex/intent-evidence-evaluation`, `a647263bcde2be074479321928b0cd74fc1c0252` | Limpio; sin diff unstaged ni staged. | Igual a `origin/codex/intent-evidence-evaluation` según el estado local tras fetch. |

Desde ese inventario, `origin/main` avanzó con el PR #8 de documentación hasta `839ae113569805da9c35ec776775a6e53ccf9e72`. La fila local de `main` y la de 003b siguen siendo una fotografía anterior; actualiza los worktrees con una nueva lectura de relaciones remotas antes de cualquier integración. El inventario no inspecciona el contenido de archivos no rastreados ni certifica su sensibilidad. No se copiaron ni publicaron esos contenidos. La tarea [AEOS-OPS-001](https://github.com/Franchute10/autonomous-agent-economy/issues/4) lleva la reconciliación. **No hacer pull, merge, rebase, reset, clean ni staging masivo** hasta comparar explícitamente los commits, revisar las diferencias y clasificar los archivos locales.

### Lo local que requiere acceso a la laptop

Esta sesión no tiene acceso directo al disco de Windows y no puede certificar el estado actual de worktrees, archivos ignorados, bases locales, logs, claves ni Docker. El siguiente paso es refrescar remotos y capturar rama, SHA y estado de cada worktree, incluyendo 003b; luego revisar cada diff y ruta no rastreada antes de seleccionar cambios. Preservar el trabajo existente: no usar `git reset`, `git clean`, `git restore` ni staging masivo. No subir credenciales, datos privados de prospección, bases locales, cachés, entornos virtuales ni reportes con información personal.

## 6. Decisiones y propuestas vigentes

### Decisiones aceptadas

1. AEOS Core permanece separado del producto satélite de búsqueda.
2. El Fix Pack de USD 5 solo puede incluir hallazgos web confirmados, evidencia, plantillas y pasos utilizables; no incluye un lead mientras no se valide.
3. El teaser rank 2/3 fue una idea de upsell, no una capacidad confiable. Queda aplazado.
4. El paquete de USD 10 con snapshot local, Porter y oportunidades es **propuesta experimental no disponible**.
5. Las búsquedas públicas deben entregar URL fuente, extracto, fecha/localidad cuando estén sustentadas, motivo de ajuste y nivel de incertidumbre.
6. Si hay cero candidatos válidos, informar cero y las limitaciones de cobertura. Nunca sustituir solicitudes por directorios, empleos, anuncios de proveedores o negocios genéricos.

### No decidido todavía

- Si y cuándo unir `codex/aeos-live-003c` con `main`, y cómo dividir los cambios para una revisión verificable.
- Si el producto que se valida primero es Fix Pack, leads, diagnóstico de mercado, o una combinación. No construir las tres ofertas en paralelo.
- Qué fuente de intención aporta volumen y calidad sin pagar un proveedor adicional ni incumplir reglas de acceso.
- Si el proceso de discovery usará agentes LLM; hasta ahora la búsqueda del motor es una cadena de consultas más filtros deterministas, no un equipo autónomo de agentes.
- Cuál será el experimento de mercado, su muestra, métricas de utilidad y decisión kill/iterate/promote.

## 7. Ruta de trabajo para salir del ciclo de prompts

### Fase 0 — Consolidación y control

1. Integrar este manual mediante PR y establecerlo como punto de entrada.
2. Hacer el inventario actual de laptop/worktrees y asociar cada cambio local con repo, rama, SHA, propósito, sensibilidad, pruebas y destino.
3. Resolver la pila de PR del motor (base, conflictos, CI y alcance), y revisar PR #1/#2 de AEOS para decidir qué preservar. No mezclar cambios en un commit masivo.
4. Actualizar el status solo con evidencia actualizada; marcar los reportes históricos como tales.

**Criterio de salida:** una rama activa por entrega, cambios locales identificados, PRs con base explícita y ningún secreto/dato de cliente en el diff.

### Fase 1 — Validación de valor antes de ampliar código

1. Elegir un caso, una zona y un segmento con una empresa piloto que pueda juzgar utilidad.
2. Definir antes de buscar qué cuenta como oportunidad útil, qué páginas y fuentes están permitidas, cómo se etiquetan resultados y cuál es el conjunto manual de referencia.
3. Ejecutar la evaluación ya documentada con el presupuesto/plan gratuito disponible y registrar costes, precisión etiquetada, cobertura temporal/geo, URL correcta y valoración del negocio.
4. Parar o cambiar el canal si los criterios acordados no se alcanzan. No ampliar filtros para hacer que las métricas se vean mejor.
5. Hacer una prueba explícita de disposición a pagar. Una compra Sandbox comprueba integración técnica; no valida demanda comercial.

**Criterio de salida:** oportunidades confirmadas por personas con URL y fuente correctas, utilidad confirmada por el negocio y evidencia suficiente para decidir si se construye el paquete pagado.

### Fase 2 — Producto y flujo de entrega

Solo después de validar la Fase 1, decidir una oferta concreta y verificar el recorrido completo: entrada, generación, evidencia, precio, checkout Sandbox, webhook, entrega idempotente y seguimiento del resultado. Mantener USD 10 oculto/no disponible hasta que el producto esté implementado y probado. No desplegar Live ni hacer cargos reales sin una decisión posterior específica.

### Fase 3 — Continuar AEOS Core

Retomar el roadmap técnico desde el último estado verificado en GitHub, no desde el último prompt. El siguiente incremento arquitectónico debe demostrar un workflow/experimento completo con ejecutor falso y reglas de autorización, reserva, ledger, evidencia, pausa/reanudación y recuperación, sin hacer depender la prueba de un LLM real. Después medir qué falta para adaptadores reales. Cada paso debe vincularse con los ADR y tener criterios de aceptación.

## 8. Protocolo de trabajo y handoff

### Fuente de verdad por tipo de dato

| Pregunta | Fuente |
|---|---|
| ¿Qué quiere ser AEOS? | Este manual, sección 2; Charter y arquitectura aprobada. |
| ¿Qué se decidió en arquitectura? | ADR aceptados y arquitectura técnica; cualquier cambio requiere ADR/Architecture Change Request. |
| ¿Qué código existe? | Rama y SHA concretos del repo, tree/diff y pruebas sobre ese SHA. |
| ¿Qué falta hacer? | Issues/PR y roadmap de este manual con estados y criterios explícitos. |
| ¿Qué cambió en laptop? | Inventario local del operador; no se infiere desde GitHub ni desde un chat. |
| ¿Qué dijo Claude/Grok u otro modelo? | Recomendación externa a revisar; solo se incorpora tras contrastarla y registrar una decisión. |

### Flujo de cada tarea

- ID único y estado: `PROPOSED`, `IN_PROGRESS`, `BLOCKED`, `DONE_REPORTED`, `DONE_VERIFIED` o `SUPERSEDED`.
- Tarea pequeña con resultado, exclusiones, archivos esperados y criterios de aceptación verificables.
- Un worktree y una rama dedicados; registrar repo, base SHA, head SHA y PR.
- Antes de integrar: revisar diff completo, seguridad/datos, pruebas pertinentes y CI sobre el SHA actual.
- El informe de cierre distingue validación local, CI, prueba externa y validación comercial.
- Actualizar este manual o el issue/PR con estado y siguiente acción. No dejar el único contexto en un chat.

### Roles de herramientas

- **ChatGPT / Director de proyecto:** reconstruye alcance, mantiene riesgos y decisiones, redacta tareas de aceptación y revisa reportes. No inventa el estado del disco local.
- **Codex:** implementa solo la tarea aprobada en su repo/worktree y devuelve evidencia reproducible.
- **Claude, Grok u otra LLM:** revisión o crítica; no crean autoridad ni reemplazan fuentes/decisiones.
- **GitHub:** registro duradero de código, ADR, issues, PR, CI y handoffs.
- **MCP:** es una interfaz de acceso entre un agente y una herramienta/servicio. No sustituye este manual, el control de versiones, las pruebas ni la gestión del proyecto.

## 9. Cómo actualizar este manual

Actualizar la fecha y el estado solo cuando haya evidencia nueva. Mantener enlaces a commits, PR, issue o documentos. No borrar estados previos de un experimento: añadir resultado, decisión y motivo. Si cambia el propósito, límites de autoridad o arquitectura, crear una revisión del Charter/ADR y explicar qué lo reemplaza.

