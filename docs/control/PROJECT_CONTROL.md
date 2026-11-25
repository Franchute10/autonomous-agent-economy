# AEOS — Control de producto

Actualizado: 2026-11-24 (America/Lima).

## Prioridad vigente: AEOS Starter

El objetivo activo es entregar **un único producto SaaS AEOS Starter v0.1 para Perú**, con autonomía supervisada. No construir planes Growth/Business ni billing recurrente en este MVP.

Fuente de verdad:
- [Starter control center](../starter/README.md)
- [Plan del MVP](../starter/AEOS_STARTER_MVP_PLAN.md)
- [Roadmap](../starter/ROADMAP.md)
- [Decisiones](../starter/DECISION_LOG.md)
- [Pruebas](../starter/TEST_LEDGER.md)
- [Release checklist](../starter/RELEASE_CHECKLIST.md)
- [Issue #49](https://github.com/Franchute10/autonomous-agent-economy/issues/49)

**Estado:** baseline de planificación integrado en main mediante commit `db041a62b5dd84543695e8f953d1b254c42c299e`; checkpoint de producto completado. Comercial es el único departamento con workflow completo previsto para v0.1; todos los departamentos serán visibles en el catálogo. Fecha objetivo confirmada: 2026-12-24, sujeta a gates y no garantizada. Gasto incremental: USD 0 hasta aprobación expresa.

**Siguiente acción:** revisar y aprobar la arquitectura candidata del [spike S0-03](../starter/S0-03_TECHNICAL_SPIKE.md). Después, consultar el coste de un proyecto Supabase aislado y aprovisionar solo si el coste y la autorización cumplen el presupuesto. No desplegar ni consumir modelos pagados antes de esa aprobación.

AEOS LIVE / diagnóstico web / pilotos de oportunidades de EE. UU. quedan preservados como línea experimental separada y pausada respecto al Starter. No mezclar sus clientes, fuentes ni métricas con el producto peruano.

---

## Archivo histórico: control del piloto LIVE (2026-11-21)

Actualizado: 2026-11-21 (America/Lima).
Entrada vigente: [NEXT_SESSION_HANDOFF.md](NEXT_SESSION_HANDOFF.md). Ejecución: [LUNA_EXECUTION_PLAN.md](LUNA_EXECUTION_PLAN.md).

## Alcance confirmado
El negocio aporta una URL o Google Business; recibe diagnóstico gratuito sustentado y prompt de corrección; puede adquirir oportunidades útiles cuando existan y estén calificadas. Productos y servicios, sin especialización obligatoria en limpieza.
USD 5 por 2–3 y USD 10 por 5–6 oportunidades son hipótesis del propietario. La cantidad real, precio y viabilidad económica requieren prueba. No vender directorios como compradores ni llenar cupos con resultados irrelevantes.
El diagnóstico cubre señales observables; no certifica indexación, posiciones, tráfico o ingresos. Google Business requiere fuente autorizada o evidencia del propietario.
El capital conceptual de la tesis no autoriza gasto: presupuesto incremental actual USD 0.

## Prioridades
| Entrega | Registro | Cierre |
|---|---|---|
| Diagnóstico real | [AEOS #38](https://github.com/Franchute10/autonomous-agent-economy/issues/38), LUNA-001 | Producto y servicio con evidencia; errores de acceso separados de hallazgos |
| Fuentes útiles | [Motor #4](https://github.com/Franchute10/commercial-lead-engine/issues/4), LUNA-002 | Solicitudes originales, ajuste, vigencia, vía de respuesta y utilidad evaluados |
| Integración mínima | LUNA-003; crear subtask bajo #38 al habilitarla | Perfil confirmado y evidencia intercambiada sin pérdida entre repositorios |
| Oferta y entrega | LUNA-004; subtask bajo #38 al habilitarla | Disponibilidad antes de cobro; entrega estable del resultado comprado en Sandbox |
| Piloto | LUNA-005; subtask bajo #38 al habilitarla | Tres negocios evalúan uso; compra real solo tras decisión específica |
| Reconciliación | [AEOS #4](https://github.com/Franchute10/autonomous-agent-economy/issues/4) | Destino de cambios pendiente documentado; no bloquea pruebas aisladas remotas |

No abrir otra ronda general de ordenamiento. Corregir documentación únicamente cuando una contradicción afecte a la tarea activa. La revisión de 34 diferencias está completada; no equivale a reconciliar todo el equipo del operador.

## Piloto comercial actual — 2026-11-21
Perfiles de prueba iniciales en EE. UU.: Construction Nation Group (sitio público en DFW/Plano; el dueño refiere Dallas/Nation Construction) y CMIMBELA Cleaning LLC (Sarasota; dictado reciente “Seminvela”). Usar evidencia del sitio y del propietario; conservar las diferencias de grafía hasta confirmar. No usar Mega Cerámicos, Lumen o AC Moreno en la validación de este piloto. Búsqueda y evidencia deben ser de EE. UU.; el análisis de compras peruanas queda como experimento independiente y fuera de sus métricas. LinkedIn aún no está decidido ni autorizado como fuente/integración.

## Decisiones de dirección — 2026-11-21
- El propietario amplió el encargo: Astra también ejecuta correcciones y experimentos acotados. El modelo disponible continúa desde el handoff; ver ASTRA_EXECUTION_2026-11-21.md y PR #42/#45.
- Priorizar evidencia de valor antes de ampliar arquitectura, fuentes o pagos.
- Conservar AEOS Core separado del motor; integración por contrato acotado.
- La experiencia objetivo comienza con una URL; pedir oferta/mercado solo si faltan o son ambiguos.
- El prompt de corrección pertenece al diagnóstico gratuito. El Fix Pack existente queda como experimento separado, sin prioridad comercial sobre leads.
- No exigir Porter, PDF, dashboards, múltiples LLM, automatización de outreach ni nuevos agentes para el primer piloto.
- No tratar web/Facebook/Nextdoor como fuentes independientes si todas se consultan a través del mismo proveedor.
- Cero oportunidades es un resultado válido; no habilitar compra de un paquete que no existe.
- Agensi es una posible distribución posterior de un skill demostrable; no demuestra demanda ni reemplaza la validación de este producto.

## Corte de ejecución — 2026-11-21
PR #42 y #45 integrados en LIVE (de2d211bc22cbbbe72b615e7434e649feca1b730). CI final: 953 passed / 12 skipped; lint, formato y tipos aprobados. Dos diagnósticos reales ejecutados desde GitHub Actions: un sitio de productos y otro de servicios, tres páginas cada uno. LUNA-001 completado a nivel de servicio con límites documentados; UI/DOM e ingesta autorizada de Google Business no acreditados. LUNA-002 es la siguiente tarjeta.
Las muestras documentales de compras públicas peruanas (ASTRA-SOURCE-001/002) son históricas y fuera del piloto estadounidense; no cuentan como yield del producto ni como una corrida automatizada de leads. No habilita integración comercial ni cobro. [Bitácora de evidencia](ASTRA_EXECUTION_2026-11-21.md).

## Fuente y reutilización de solicitudes — 2026-11-21
ASTRA-SOURCE-002 documentó una muestra manual peruana para perfiles que no corresponden al piloto de EE. UU.; sus cero elegibles son fuera de alcance y no cuentan en la evaluación comercial actual. Workana queda fuera del feed AEOS: sus términos oficiales restringen la minería de datos y la redistribución/reventa de contenido. No alimentar paquetes pagos desde marketplaces sin licencia explícita.
LUNA-002 permanece en curso: elegir fuentes estadounidenses permitidas para Construction Nation Group y CMIMBELA Cleaning LLC, perfil por perfil, con evidencia original vigente y coste incremental USD 0. No se contactó a nadie. Evidencia: [bitácora](ASTRA_EXECUTION_2026-11-21.md) y [Motor #4](https://github.com/Franchute10/commercial-lead-engine/issues/4).

## Fuente de verdad
GitHub conserva tareas, decisiones, código y evidencia resumida. Un documento describe intención; el SHA y la prueba acreditan implementación; la revisión humana acredita utilidad; una transacción real acredita una compra.
Main contiene el control canónico. LIVE contiene una línea candidata aún no integrada a main. Verificar ambos antes de editar; no confundir merge a LIVE con release.

Al cerrar cada tarea: registrar ID, estado, fecha, repo/rama/SHA, PR, pruebas con denominadores, evidencia real o sintética, decisión y siguiente acción. No marcar DONE por escribir un plan.
