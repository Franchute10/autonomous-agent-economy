# AEOS — Control de producto y continuidad

Fecha: 2026-11-20, America/Lima. Dirección confirmada por Frank. Este documento actualiza la prioridad de producto; las cifras históricas del handbook no son el estado vigente.

## Objetivo y alcance

AEOS conserva la investigación original: una organización gobernada de agentes con recursos limitados (ejemplo conceptual: USD 50), capaz de experimentar, generar valor, aprender y sostenerse. El presupuesto conceptual no autoriza gasto.

Prioridad de ejecución: un negocio de productos o servicios aporta su sitio web o Google Business; recibe diagnóstico gratuito con evidencia y un prompt para corregir su web; después puede adquirir oportunidades comerciales útiles. Metas experimentales del propietario: USD 5 por 2–3 leads y USD 10 por 5–6. Precio y cantidad se validarán con disponibilidad, utilidad, coste y compras reales. No reemplazar esta meta por un informe genérico ni vender directorios como solicitudes de compradores.

El diagnóstico evalúa HTML, estructura, robots, sitemap, metadatos y señales observables dentro de su cobertura. No certifica indexación, tráfico, posiciones ni resultados económicos. Google Business requiere una fuente autorizada o evidencia del dueño; el flujo actual solo reconoce la URL y solicita esa evidencia.

La limpieza interior es un caso histórico. No limita el producto, la taxonomía ni las pruebas. Manatee permanece descartado por capacidad técnica; PMI/iTrip/Turno son opciones de ese piloto, no el siguiente paso obligatorio de toda la plataforma. LIVE-003C2 queda subordinado al objetivo transversal de producto.

## Fuentes y responsabilidades

- AEOS: núcleo, diagnóstico, experiencia de producto, presupuestos, gobernanza e integración.
- Commercial Lead Engine: búsqueda, evidencia, evaluación de intención y calidad. La integración entre repositorios sigue pendiente; no se acredita un pipeline completo de agentes.
- Frank: decisiones comerciales, presupuesto y validación de utilidad con empresas.
- Agente ejecutor: implementación, pruebas, commits, informe de evidencia y siguiente acción.
- Revisor: verificar diff, fuente, alcance y resultados antes de promoción.

## Tablero de ejecución

| ID | Entrega | Estado / dependencia | Criterio de cierre |
|---|---|---|---|
| OPS-001 | Reconciliar laptop y parches | [Issue existente #4](https://github.com/Franchute10/autonomous-agent-economy/issues/4), parcial | Cada cambio tiene destino; respaldo antes de archivar; revisar 34 diferencias de main y datos locales |
| PRODUCT-001 | Diagnóstico gratuito y prompt para varios rubros | [Issue #38](https://github.com/Franchute10/autonomous-agent-economy/issues/38), en progreso | Sitio real de productos y de servicios, hallazgos atribuibles y prompt usable; Google Business con evidencia autorizada |
| PRODUCT-002 | Corregir selección de páginas de productos | [PR #39](https://github.com/Franchute10/autonomous-agent-economy/pull/39); cuatro pruebas realizadas | Productos/catálogo/servicios/ofertas inspeccionados dentro del presupuesto, sin asumir limpieza |
| LEADS-VAL-001 | Validar solicitudes útiles y coste | [Motor #4](https://github.com/Franchute10/commercial-lead-engine/issues/4), pendiente de fuente accesible | Un sector de productos y dos de servicios; URLs originales revisadas, fechas/zonas verificables, utilidad y coste por lead |
| DELIVERY-001 | Cobro y entrega consistente | Dentro de PRODUCT-001; revisar PR AEOS #1/#2 | Pago de prueba entrega exactamente el resultado comprado; firmas, idempotencia, recuperación y tratamiento de falta de stock |
| RELEASE-001 | Piloto pagado | Depende de PRODUCT, LEADS y DELIVERY | Empresa recibe valor confirmado; transacción real autorizada y margen medido |

No abrir otra ronda general de documentación si la siguiente tarea ejecutable ya está identificada. El orden es: corrección concreta → staging con red → evaluación de calidad de fuentes → entrega pagada de prueba → piloto comercial. La revisión del trabajo local continúa como tarea independiente y no bloquea pruebas aisladas sobre versiones remotas limpias.

## Decisiones de esta sesión

1. Alcance de productos y servicios confirmado por el propietario; no prometer cobertura universal ya implementada.
2. Continuidad en GitHub: objetivo, tareas, decisiones, pruebas y límites tienen archivo e issue; el chat sirve de interfaz.
3. No aplicar paquetes de parches antiguos en bloque. Comparar cada archivo contra la rama correspondiente.
4. Mantener historial local y datos privados hasta poder inspeccionarlos en Windows. No afirmar que la laptop quedó limpia desde este entorno remoto.
5. Las métricas comerciales permanecen sin verificar: pruebas offline no demuestran leads reales ni disposición a pagar.
6. El Fix Pack existente es una capacidad experimental separada; no sustituye automáticamente los paquetes de leads definidos por el propietario.

## Cómo continuar desde cualquier modelo

Leer README → PROJECT_READINESS → este plan → VALIDATION_2026-11-20 → issue de la tarea → archivos de código. Confirmar repo, rama, SHA y estado; leer AGENTS.md. Elegir una tarea abierta con criterios de aceptación. Ejecutar, probar y registrar el resultado en GitHub antes de terminar. Si una dependencia impide ejecutar, escribir qué evidencia falta y avanzar una tarea independiente.

Cada entrega debe registrar: ID, objetivo, archivos, base y commit/PR, pruebas con denominadores y skips, evidencia live vs fixture, decisión, riesgos observados y siguiente acción. No marcar DONE por haber escrito un plan. Mantener una rama por entrega y un solo registro vigente; conservar historia fechada sin llamarla estado actual.

Siguiente acción concreta: probar el diagnóstico corregido en staging con DNS/red pública; evaluar por separado las fuentes de intención con un conjunto etiquetado de productos y servicios. La corrida local falló antes de leer robots.txt y no permite juzgar las webs. Ningún dato faltante debe suplirse con leads sintéticos.
