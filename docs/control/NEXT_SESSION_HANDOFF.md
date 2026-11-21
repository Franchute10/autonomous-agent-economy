# AEOS — Continuidad vigente
Actualizado: 2026-11-21 (America/Lima). Planificación Astra; ejecución posterior con Luna.

## Retomar
1. Leer este archivo y [el plan ejecutable para Luna](LUNA_EXECUTION_PLAN.md).
2. Verificar issues, ramas y SHAs actuales; leer AGENTS.md y PROJECT_HANDBOOK.md antes de editar.
3. Ejecutar solo la siguiente tarjeta habilitada. No pedir nuevamente los chats completos.
4. Registrar el resultado en GitHub al completar o bloquear cada tarea.

Este archivo gobierna la siguiente acción; [PROJECT_CONTROL.md](PROJECT_CONTROL.md) fija el alcance. El handbook, readiness y documentos de oferta anteriores conservan historia, pero sus estados y prioridades fechados no sustituyen este corte. Las decisiones arquitectónicas aceptadas siguen vigentes.

## Objetivo
URL o Google Business de un negocio de productos o servicios → diagnóstico gratuito con evidencia y prompt de corrección → oportunidades comerciales útiles, disponibles antes de ofrecer su compra.
USD 5 por 2–3 oportunidades y USD 10 por 5–6 son hipótesis por validar. No restringir AEOS a limpieza; no prometer cobertura universal. Presupuesto incremental autorizado: USD 0.
AEOS conserva su propósito de organización gobernada de agentes. Ampliar el runtime no es requisito previo para validar esta oferta.

## Evidencia y límites
- Control de proyecto integrado en main mediante [PR #40](https://github.com/Franchute10/autonomous-agent-economy/pull/40), merge 963491a9d8f45b107c95835e097a03d2b6636a89.
- Selección de páginas de productos/servicios integrada en la rama codex/aeos-live-003c mediante [PR #39](https://github.com/Franchute10/autonomous-agent-economy/pull/39), merge f5cf0c642e36f7a493a48908164c5aba0798dc99. No equivale a integración de LIVE en main.
- PR #39 reporta validación sobre su base más el cambio: 941 passed / 12 skipped, Ruff/formato/mypy/diff check aprobados. No son pruebas nuevas de esta revisión de planificación.
- Revisión de las 34 diferencias del parche main completada; conservar LIVE. No reaplicar parches antiguos en bloque. Reconciliación restante: [AEOS #4](https://github.com/Franchute10/autonomous-agent-economy/issues/4).
- Prueba posterior: cuatro casos sintéticos pasaron mediante harness Python. El diagnóstico externo quedó bloqueado por DNS. Eso no evalúa la calidad del sitio ni demuestra leads.
- No hay todavía evidencia suficiente de oportunidades útiles repetibles, entrega comercial completa ni compras reales. Google Business sigue requiriendo evidencia autorizada.
- Motor de leads: [PR #1](https://github.com/Franchute10/commercial-lead-engine/pull/1) abierto hacia main; [PR #2](https://github.com/Franchute10/commercial-lead-engine/pull/2) abierto sobre la rama del #1. No son cambios integrados en main.
- Fix Pack es una oferta experimental distinta. No confundir su Sandbox con venta de paquetes de leads.

## Siguiente acción única
**LUNA-001: comprobar diagnóstico real acotado** en un sitio de productos y otro de servicios, desde una copia aislada de la rama LIVE verificada, con acceso de red.
Leer criterios y salida de bloqueo en LUNA_EXECUTION_PLAN.md. No modificar código ni repetir suites por rutina si solo se está capturando evidencia.
Después: LUNA-002, decidir viabilidad de fuentes antes de construir integración/cobro.

Esta revisión Astra entrega documentación y decisiones de planificación. No implementa las tarjetas ni las declara aprobadas por pruebas.

## Continuidad obligatoria
Antes de terminar cada bloque, incluso por bloqueo: actualizar el issue con ID, rama/SHA, resultado, prueba realmente ejecutada, limitación y siguiente paso. Actualizar este archivo cuando cambie la siguiente acción. Evidencia técnica pública resumida; datos de prospectos y credenciales fuera del repositorio público.
Una sesión nueva debe poder continuar con este enlace y acceso a GitHub. El modelo no cambia el alcance ni convierte una propuesta en capacidad existente.
