# AEOS — Control de producto
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
La exploración documental de seis casos produjo cero oportunidades confirmadas útiles por un dueño; no es una corrida automatizada de leads. No habilita integración comercial ni cobro. [Bitácora de evidencia](ASTRA_EXECUTION_2026-11-21.md).

## Fuente y reutilización de solicitudes — 2026-11-21
ASTRA-SOURCE-002 no encontró oportunidad elegible para los tres perfiles en la muestra manual de compras públicas. Workana queda fuera del feed AEOS: sus términos oficiales restringen la minería de datos y la redistribución/reventa de contenido. No alimentar paquetes pagos desde marketplaces sin licencia explícita.
LUNA-002 permanece en curso y debe elegir una fuente primaria autorizada, perfil por perfil, con evidencia original vigente y coste incremental USD 0. No se contactó a nadie. Evidencia: [bitácora](ASTRA_EXECUTION_2026-11-21.md) y [Motor #4](https://github.com/Franchute10/commercial-lead-engine/issues/4).

## Fuente de verdad
GitHub conserva tareas, decisiones, código y evidencia resumida. Un documento describe intención; el SHA y la prueba acreditan implementación; la revisión humana acredita utilidad; una transacción real acredita una compra.
Main contiene el control canónico. LIVE contiene una línea candidata aún no integrada a main. Verificar ambos antes de editar; no confundir merge a LIVE con release.

Al cerrar cada tarea: registrar ID, estado, fecha, repo/rama/SHA, PR, pruebas con denominadores, evidencia real o sintética, decisión y siguiente acción. No marcar DONE por escribir un plan.
