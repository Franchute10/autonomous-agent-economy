# AEOS Starter — plan de entrega del primer MVP

**ID:** AEOS-STARTER-001  
**Fecha de planificación:** 2026-11-24 (America/Lima)  
**Estado:** PROPUESTA BASELINE — pendiente de aprobación del propietario  
**Mercado inicial:** Perú  
**Modelo:** SaaS, una única oferta inicial (Starter)  
**Autonomía:** supervisada  
**Repositorio rector:** `Franchute10/autonomous-agent-economy`  
**Rama de planificación:** `product/aeos-starter-mvp-20261124`

## 1. Decisión de producto

Construir y poner en manos de usuarios un solo producto inicial: **AEOS Starter**. No construir tres planes comerciales ni un sistema de billing/suscripciones como requisito del MVP.

El MVP se considera entregado cuando una empresa peruana puede crear su espacio, cargar contexto empresarial, asignar una tarea al Orchestrator, obtener trabajo real de un agente conectado a un modelo, revisar evidencia y resultado, aprobar o rechazar una acción controlada y consultar el historial desde una interfaz web desplegada.

**No es objetivo de este MVP:** desplegar nueve departamentos con amplitud funcional completa, construir microservicios, desarrollar marketplace de agentes, habilitar autonomía sin supervisión, automatizar outreach, integrar pagos recurrentes, crear tres planes, ni terminar todas las capacidades de AEOS LIVE.

## 2. Alcance vertical y producto completo

La arquitectura y el catálogo contemplarán todos los departamentos de una empresa (Dirección, Comercial, Marketing, Atención al Cliente, Administración, Finanzas, Operaciones/Logística, Compras y RR. HH./BI como capacidades configurables). Sin embargo, para llegar a una entrega real en cuatro semanas:

- La interfaz mostrará una organización con catálogo de departamentos y agentes disponibles.
- Solo **un departamento tendrá un flujo operativo completo en el MVP**.
- Los demás departamentos quedarán representados como capacidades futuras/no activadas, sin simular que ya funcionan.
- Se recomienda que el primer flujo sea **Comercial**, porque permite probar una tarea observable de extremo a extremo: investigar una cuenta/empresa con fuentes públicas permitidas, resumir hallazgos con evidencia, preparar una oportunidad o siguiente acción y dejar un borrador para aprobación humana. No se enviarán mensajes automáticamente.
- El primer flujo podrá usar empresas y datos de prueba en Perú; los datos reales se incorporarán solo con autorización y tratamiento apropiado.

La decisión del primer departamento operativo se confirma en el primer checkpoint. Recomendación: Comercial.

## 3. Experiencia de aceptación de extremo a extremo

Un usuario administrador de una empresa peruana:

1. Abre la URL pública de AEOS Starter.
2. Crea su cuenta e inicia sesión.
3. Crea una organización y queda como administrador.
4. Completa un perfil breve de empresa (sector, productos/servicios, zona, cliente objetivo).
5. Carga un documento o introduce información de contexto.
6. Abre el espacio de trabajo y escribe una tarea en lenguaje natural.
7. El Orchestrator convierte la solicitud en un workflow delimitado y muestra qué hará.
8. El agente asignado consulta solo herramientas habilitadas y datos permitidos.
9. El sistema registra estado, fuentes, resultados, errores y consumo.
10. El usuario revisa el resultado y sus evidencias.
11. Si el flujo propone una acción externa, queda pendiente de aprobación; el usuario puede aprobar o rechazar.
12. El usuario consulta el historial de tareas y retoma una ejecución interrumpida.

Esta experiencia debe funcionar en un entorno desplegado, no solo en CLI, tests unitarios, mocks o una demo grabada.

## 4. Inventario reutilizable — confirmado en GitHub al 2026-11-24

### AEOS `main`

El `main` remoto es la única rama canónica integrada. Incluye:

- Paquetes de dominio de organización, agentes, gobernanza, economía, workflows y conocimiento.
- Definiciones tipadas/versionadas de agentes e invocaciones.
- Definiciones de workflow, nodos, aristas, runs y attempts.
- Contratos de artefactos y almacenamiento local.
- Persistencia PostgreSQL con SQLAlchemy 2.x, Unit of Work y migración inicial.
- Pruebas unitarias y de integración para los contratos existentes.

No incluye un runtime que ejecute workflows de principio a fin, un Model Gateway conectado, una API SaaS, interfaz de usuario, onboarding ni memoria empresarial integrada. Los ocho ADR existentes son decisiones aceptadas, no prueba de que todo esté implementado.

### AEOS LIVE `codex/aeos-live-003c`

SHA verificado: `de2d211bc22cbbbe72b615e7434e649feca1b730`.

Contiene capacidades de diagnóstico web, perfiles de negocio, evidencia, oportunidades, captura manual, pilotos, almacenamiento tenant-scoped para algunas entidades y una beta web de diagnóstico. La beta existente no es AEOS AI Workforce ni un runtime de empleados digitales. Su código no se debe fusionar en bloque con `main`.

Comparación consultada: LIVE está 49 commits adelante y 26 detrás de `main`; ambas ramas divergieron. La integración será selectiva, por archivo/feature y con pruebas. No hacer merge masivo ni borrar ramas/worktrees.

PR #48 sigue abierto como borrador de pruebas de software y dos sitios estadounidenses. Sus checks de 2026-11-22 pasaron, incluyendo 953 pruebas y 12 omitidas en CI; las omitidas incluyen dependencias de PostgreSQL/Playwright. Es evidencia de la línea LIVE, no aceptación del Starter. Mantener el alcance de ese PR separado.

### Commercial Lead Engine

Repositorio: `Franchute10/commercial-lead-engine`.

Es un motor CLI local-first, no un servicio HTTP, SaaS, worker ni runtime multiagente. Incluye discovery, auditoría web, scoring, evidencia, investigación de contactos, borradores de outreach y evaluación de intención pública en ramas/PR específicos. PR #1 y #2 están abiertos y apilados; la rama de evaluación tiene 35 commits adelante y 3 detrás de main. No fusionar automáticamente. Para el MVP se podrá reutilizar una capacidad mediante un adaptador explícito solo si la tarea comercial elegida lo requiere y se verifica su estado; no es dependencia inicial para demostrar el Orchestrator.

### Pendientes operativos existentes

- AEOS issue #4: reconciliación de worktrees locales y cambios no confirmados. No ejecutar reset/clean ni staging masivo.
- AEOS issue #38: producto LIVE anterior de diagnóstico/lead journey. Mantenerlo como línea histórica/experimental y no confundirlo con Starter.
- PR de pagos AEOS #1/#2: no son dependencia del Starter; no integrar ni habilitar pagos.
- No hay evidencia de un frontend SaaS de AI Workforce ya implementado ni de un Agent Runtime conectado a modelos reales.

## 5. Arquitectura objetivo mínima para Starter

Mantener **monolito modular**. Un backend desplegable y un worker/proceso de ejecución inicialmente; no microservicios.

- **Frontend:** Next.js/React + TypeScript, aplicación web responsive.
- **API:** FastAPI sobre Python 3.12+, contratos Pydantic en el borde.
- **Persistencia:** PostgreSQL, SQLAlchemy 2.x, Alembic.
- **Identidad:** proveedor de autenticación gestionado o solución probada; no inventar auth casera. Selección documentada antes de implementar.
- **Runtime:** worker con ejecución durable, estados, lease, timeout, retry limitado, idempotencia y recuperación.
- **Model Gateway:** un proveedor/modelo inicial detrás de un port; no multi-LLM en MVP.
- **Tool Gateway:** herramientas explícitas con schema, permisos, timeout y auditoría.
- **Knowledge:** perfil empresarial + documentos/artefactos. Búsqueda textual básica; no vector DB obligatoria.
- **Audit:** actor, tenant, acción, hora, estado, versión de agente/modelo y referencias de evidencia.
- **Deployment:** un entorno de staging y uno de producción, con secretos gestionados, HTTPS, backups y health checks.
- **Observabilidad:** logs estructurados, errores y consumo por ejecución.

### Reglas de seguridad

- Cada registro de negocio y artefacto privado pertenece a un `organization_id`.
- Identidad del tenant se deriva de la sesión autenticada, nunca de un valor libre enviado por el browser.
- Aplicar autorización en el servicio y RLS en todas las tablas privadas tenant-owned antes de aceptar clientes externos.
- No exponer credenciales de base de datos ni acceso SQL al frontend/agentes.
- Contenido de documentos y web es dato no confiable, no instrucciones del sistema.
- Acciones externas requieren aprobación humana explícita.
- Sin envío automático de emails/WhatsApp/LinkedIn, pagos, compras, contratos ni modificaciones de sistemas de clientes.
- Presupuestos y límites por ejecución; no llamadas ilimitadas.
- No cargar datos personales reales en repositorio público, fixtures, logs o demos.

## 6. Plan de entrega — 24 hitos verificables

Las semanas son estimaciones de ejecución con un desarrollador principal asistido por agentes de código y revisión del propietario. Cada hito debe tener issue/PR, commit, pruebas y estado. Los hitos pueden ejecutarse en paralelo solo cuando no exista dependencia técnica.

| ID | Semana | Hito | Criterio de salida |
|---|---:|---|---|
| S0-01 | 0 | Baseline de repositorios y ramas | SHA, ramas, PR, árbol de archivos y riesgos registrados; ningún worktree local alterado |
| S0-02 | 0 | Cerrar decisiones de producto Starter | Documento aprobado; un único MVP, sin tiers ni billing |
| S0-03 | 0 | Spike de auth/deployment/DB | Elección justificada, app mínima desplegada y conexión PostgreSQL de staging probada |
| S1-01 | 1 | Integración selectiva de Core | Branch de producto desde main; código reusable cherry-picked/portado con evidencia |
| S1-02 | 1 | Tenant + usuarios + organización | Registro/login, crear organización, membership y autorización |
| S1-03 | 1 | Seguridad multi-tenant | Tests cross-tenant de API/DB/RLS pasan con PostgreSQL real |
| S1-04 | 1 | Perfil empresarial y artefactos | Crear/editar perfil, subir, listar y descargar un documento aislado por tenant |
| S1-05 | 1 | Primer frontend desplegado | Login, onboarding y dashboard navegables en staging |
| S2-01 | 2 | Agent Registry Starter | Registrar agente versionado, propósito, capacidades y límites |
| S2-02 | 2 | Model Gateway | Un modelo real conectado mediante port; timeout, errores y límites probados |
| S2-03 | 2 | Tool Gateway mínimo | Herramientas allowlisted, schemas, validación y auditoría |
| S2-04 | 2 | Runtime durable | Crear ejecución, reclamar tarea, actualizar estado y recuperar tras reinicio |
| S2-05 | 2 | Orchestrator v1 | Recibir instrucción, generar plan estructurado y solicitar confirmación antes de ejecutar |
| S2-06 | 2 | Centro de trabajo | Lista de tareas, detalle, estados, salida y errores |
| S3-01 | 3 | Departamento inicial | Comercial (recomendado) con un workflow completo y acotado |
| S3-02 | 3 | Evidencia y memoria de tarea | Fuentes, documentos consultados, resultado y referencias persistidas |
| S3-03 | 3 | Aprobación humana | Aprobar/rechazar acción propuesta; decisión queda auditada |
| S3-04 | 3 | Historial y recuperación | Ver ejecuciones pasadas y reanudar las recuperables sin duplicar efectos |
| S3-05 | 3 | Consumo y límites | Tokens/uso estimado por tarea, cuota configurable y bloqueo al exceder límite |
| S4-01 | 4 | Hardening funcional | Flujos de error, validación de inputs, límites, idempotencia y permisos |
| S4-02 | 4 | Pruebas E2E con PostgreSQL | Recorrido completo de signup a resultado/aprobación en staging |
| S4-03 | 4 | Piloto cerrado en Perú | 2–3 usuarios/empresas prueban tareas reales autorizadas |
| S4-04 | 4 | Release Starter v0.1 | URL estable, guía de uso, changelog, soporte y checklist de release |

## 7. Cronograma propuesto

Inicio de planificación: martes 24 de noviembre de 2026.

- Semana 0 — 24 al 27 nov: baseline, alcance, decisión del primer workflow, spike de infraestructura.
- Semana 1 — 30 nov al 4 dic: tenant, autenticación, perfil, documentos y primera UI.
- Semana 2 — 7 al 11 dic: Model Gateway, Tool Gateway, runtime y Orchestrator.
- Semana 3 — 14 al 18 dic: workflow del departamento inicial, evidencias, aprobación e historial.
- Semana 4 — 21 al 24 dic: hardening, E2E, piloto cerrado y release v0.1.

**Fecha objetivo:** 24 de diciembre de 2026 para Starter v0.1, condicionada a acceso a hosting, base de datos y proveedor/modelo IA, más disponibilidad de un desarrollador que ejecute y pruebe los cambios. Si esos accesos no están disponibles en semana 0, registrar bloqueo y nueva previsión; no esconderlo extendiendo tareas silenciosamente.

### Entrega temprana obligatoria

No esperar a la semana 4 para ver algo funcionando:

- 27 nov: primera URL de staging con pantalla de acceso/estado de la app.
- 4 dic: usuario puede ingresar, crear empresa y cargar perfil/documento.
- 11 dic: usuario puede enviar una tarea y ver una ejecución real del modelo en el centro de trabajo.
- 18 dic: un workflow departamental completo con evidencia y aprobación.
- 24 dic: release candidato Starter v0.1 y piloto cerrado.

Si al 11 de diciembre no hay tarea real ejecutándose desde la UI, detener ampliaciones y reducir alcance hasta que ese recorrido funcione.

## 8. Criterios de aceptación del MVP

No declarar MVP listo por pasar pruebas unitarias solamente. Todos los siguientes criterios deben probarse en staging desplegado:

1. Un usuario puede registrarse, iniciar sesión y crear una organización.
2. Un usuario no puede leer ni modificar datos de otra organización; pruebas con PostgreSQL/RLS real.
3. Puede completar el perfil empresarial y cargar un documento.
4. Puede iniciar una tarea desde la UI.
5. La tarea crea una ejecución durable vinculada al tenant y al usuario.
6. Un agente invoca un modelo real a través del Model Gateway.
7. El runtime muestra estados y maneja errores/timeouts.
8. El resultado se guarda y se puede abrir después de cerrar sesión y volver a entrar.
9. Las afirmaciones relevantes incluyen referencias a fuente/documento o quedan marcadas como inferencia/no verificadas.
10. Las herramientas disponibles son allowlisted y no pueden exceder sus permisos.
11. Las acciones externas esperan aprobación y registran aprobar/rechazar.
12. Reiniciar el worker no pierde ejecuciones ni duplica efectos.
13. El consumo queda registrado y los límites detienen nuevas llamadas.
14. Un piloto completa una tarea útil y el usuario puede calificar su resultado.
15. Hay una URL estable, guía breve, política de datos y procedimiento de soporte.

## 9. Exclusiones expresas para proteger la fecha

- No crear planes Growth/Business ni suscripciones/pagos recurrentes.
- No desarrollar los nueve departamentos en profundidad; solo uno tendrá workflow operativo completo.
- No construir agentes que se comuniquen libremente entre ellos.
- No desarrollar multi-LLM, marketplace, app móvil nativa, WhatsApp, LinkedIn ni outreach automático.
- No incorporar vector database, Redis, Kubernetes o microservicios sin evidencia de necesidad.
- No fusionar LIVE completo ni el Commercial Lead Engine completo.
- No ampliar el piloto estadounidense de LIVE; Starter valida el mercado peruano por separado.
- No reabrir diagnóstico web/lead sales como producto central del Starter.
- No invertir en branding avanzado antes de disponer de un flujo funcional.

## 10. Gestión del proyecto y continuidad

GitHub es la fuente de verdad del proyecto. El chat sirve para conversar, priorizar y tomar decisiones; nunca será el único lugar donde existan objetivos, tareas o estado.

### Archivos de control obligatorios

- `docs/starter/PRODUCT_BRIEF.md`: problema, usuario, promesa, alcance y exclusiones.
- `docs/starter/ROADMAP.md`: hitos, fechas, dependencias y estado.
- `docs/starter/DECISION_LOG.md`: decisiones y cambios aprobados.
- `docs/starter/TEST_LEDGER.md`: pruebas, SHA, resultado, denominador, skips y evidencia.
- `docs/starter/RELEASE_CHECKLIST.md`: aceptación y release.
- `docs/control/NEXT_SESSION_HANDOFF.md`: resumen de continuidad y próxima acción.
- Issues GitHub: una tarjeta por bloque de trabajo con aceptación.
- Pull requests: cambios revisables, ligados a issue, CI y evidencia.

### Reglas de operación como gerente de proyecto TI

1. Antes de trabajar: revisar estado de GitHub, issue activo, rama, SHA, PR y CI.
2. Trabajar un objetivo acotado por PR; no mezclar documentación, infraestructura y features no relacionadas.
3. Registrar en cada issue: objetivo, alcance/no alcance, dependencias, aceptación, evidencia y siguiente paso.
4. Actualizar ROADMAP y TEST_LEDGER al cerrar cada hito.
5. Cada commit debe tener mensaje descriptivo y pertenecer a una rama de trabajo.
6. Cada PR debe indicar issue, cambios, pruebas ejecutadas, limitaciones y cómo probar manualmente.
7. No marcar DONE por haber escrito código: exigir CI y aceptación del usuario cuando corresponda.
8. Si una tarea se bloquea más de medio día, registrar causa, alternativa y decisión requerida; continuar con tareas independientes.
9. Mantener un máximo de dos tareas técnicas activas en paralelo.
10. No hacer merge, borrar ramas, reset, clean ni tocar worktrees locales sin inspección y autorización.
11. No subir datos personales, secretos, bases locales, prospectos ni documentos de clientes.
12. Actualizar handoff al final de cada sesión o antes de cambiar de agente/chat.

### Formato obligatorio de actualización

- ID / hito:
- Estado: TODO | IN_PROGRESS | BLOCKED | IN_REVIEW | DONE
- Fecha:
- Repositorio / rama / SHA:
- Issue / PR:
- Cambios realizados:
- Pruebas ejecutadas (comando, entorno, denominador, skips):
- Evidencia:
- Riesgos/bloqueos:
- Decisión requerida:
- Siguiente acción única:

## 11. Riesgos y condiciones de calendario

- **Integración de ramas:** LIVE diverge de main. Mitigación: branch Starter desde main y cherry-pick selectivo con pruebas.
- **Autenticación y aislamiento:** RLS parcial en LIVE y sin SaaS auth. Mitigación: PostgreSQL real y pruebas cross-tenant como gate antes de pilotos externos.
- **Runtime no implementado:** el dominio de workflow no equivale a ejecución. Mitigación: spike temprano, fake executor primero, luego un modelo real.
- **Proveedor de IA:** faltan credenciales/cuenta y política de datos confirmadas. Mitigación: un proveedor inicial, secreto fuera de Git y presupuesto máximo aprobado.
- **Hosting/DB:** no seleccionar ni pagar infraestructura sin comparar opciones y aprobación de gasto. Mitigación: spike en semana 0.
- **Alcance:** todos los departamentos podrían expandirse indefinidamente. Mitigación: un solo workflow completo para Starter v0.1.
- **Capacidad de ejecución:** el cronograma presupone una persona técnica ejecutando cambios y revisiones frecuentes; agentes IA aceleran, pero no reemplazan pruebas y despliegue reales.

## 12. Próxima acción

**STARTER-00 — Product scope checkpoint.**

1. Confirmar que el primer workflow operativo será Comercial (recomendado) u otro departamento.
2. Confirmar que aceptamos nueve departamentos visibles en el catálogo, pero solo uno funcional de extremo a extremo en v0.1.
3. Confirmar la fecha objetivo del 24-12-2026 como objetivo de trabajo, no garantía.
4. Confirmar el presupuesto incremental permitido para hosting y modelo IA. Hasta entonces, gasto incremental autorizado: USD 0.

Después del checkpoint, convertir los 24 hitos en issues de GitHub, iniciar el spike de despliegue y no ampliar alcance sin una decisión registrada.
