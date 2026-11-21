# AEOS — Continuidad vigente
Actualizado: 2026-11-21, 17:18 (America/Lima). Planificación y ejecución focal; continuar con el modelo disponible.

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

## Estado verificado
| Entrega | Evidencia | Alcance real |
|---|---|---|
| Control y continuidad en main | PR #40 merge 963491a9; PR #41 merge 87055066; actualización documental PR #43 | Main conserva la dirección; LIVE sigue separada |
| Selector multisector | PR #39, merge f5cf0c64 | Rutas de productos, catálogos y servicios |
| Perfiles y ajuste de productos | PR #42, merge 548ed0c2; CI 949 passed / 12 skipped | Catálogo sin servicios y ajuste por products; no todos los formularios |
| Diagnóstico real | Runs 44955224788 y 44955755471 | Mega Cerámicos y Lumen: 3 páginas cada uno, SUCCEEDED; ejecución del programa, no lectura por buscador |
| Muestreo y prompt corregidos | PR #45, merge de2d211bc22cbbbe72b615e7434e649feca1b730; CI 44955889071: 953 passed / 12 skipped; lint/formato/mypy PASS | Rutas distintas antes de variantes; comparar contenido antes de cambiar metadatos |
| Google Business | Prueba local con entrada sintética | OWNER_EVIDENCE_REQUIRED, 0 páginas; no inspección real ni ingesta implementada |
| Exploración de fuentes | [Bitácora](ASTRA_EXECUTION_2026-11-21.md), ASTRA-SOURCE-001 | 6 casos: 3 candidatos documentales, 1 vencido, 2 conflictos; 0 útiles confirmados por dueño |

LIVE verificada: `codex/aeos-live-003c` en `de2d211bc22cbbbe72b615e7434e649feca1b730`. Resolver SHA actual antes de editar.
Mega Cerámicos: sin hallazgos confirmados en la muestra, H1 pendiente. Lumen: descripción repetida en portada, contacto y about, con evidencia y prompt condicionado. No se certifica SEO completo, DOM, UI, conversión ni rentabilidad.
PR #44 está cerrado sin merge, como experimento completado y reemplazado por #45. La primera CI de #45 falló por formato del fixture; el head final pasó. No usar el fallo antiguo como bloqueo vigente.
La prueba real usa runner estándar del repo público, URLs fijas, sin secretos/API pagada/contacto ni cron. El entorno local sigue con limitaciones DNS/dependencias; no volver a declararlo bloqueo global.

## Pendientes preservados
- Revisión de 34 diferencias completada; no reaplicar parches. Reconciliación de laptop aún en [AEOS #4](https://github.com/Franchute10/autonomous-agent-economy/issues/4); no reset/clean ni staging masivo.
- Motor: PR #1 hacia main y PR #2 sobre la rama del #1 siguen como pila abierta en el último corte; verificar antes de editar. La base de evaluación documentada es a647263bcde2be074479321928b0cd74fc1c0252.
- No hay generación repetible de oportunidades útiles, venta de leads ni entrega comercial completa demostradas.
- AEOS PR #1/#2 de pagos requieren revisión separada. Entrega futura debe recuperar el resultado comprado inmutable; no rediagnosticar para reconstruirlo.
- Las pruebas reales y fuentes públicas están resumidas en la bitácora. Datos privados de prospectos, credenciales y journals no van al repo público.

## Siguiente acción única — LUNA-002 / LEADS-VAL-001
Registro: [commercial-lead-engine #4](https://github.com/Franchute10/commercial-lead-engine/issues/4).
**Objetivo:** decidir si una fuente produce solicitudes pertinentes para un negocio real antes de integrar otra API o vender un paquete.

1. Recuperar de la evidencia existente tres fichas: un negocio de productos y dos de servicios. Fijar oferta, capacidad confirmada, zona, idioma, ventana y exclusiones. Solicitar únicamente datos imprescindibles ausentes; no inventarlos.
2. Congelar fuente/consultas/límite antes de la corrida. Los seis casos documentales previos no equivalen a tres corridas comparables ni a leads para esos negocios.
3. Revisar originales y registrar necesidad, fecha/estado, ajuste, vía legítima de respuesta y descartes. Separar candidatos documentales de oportunidades útiles confirmadas.
4. Si una cuota de API no puede acreditarse gratuita, continuar evaluación manual acotada y marcar automatización bloqueada; no gastar ni contratar.
5. Preparar muestra privada para valoración del dueño solo con candidatos elegibles. Sin oportunidades suficientes, registrar cero y cambiar fuente/segmento tras el límite del experimento. No sustituir solicitudes por directorios.
6. Actualizar Motor #4, bitácora y este archivo con resultado y siguiente paso.

LUNA-003/004/005 siguen condicionadas a la utilidad demostrada. LUNA-001 no necesita repetirse por cambiar de chat o modelo. No abrir otra ronda general de documentación.

## Continuidad obligatoria
Cada bloque deja ID/estado, fecha, repo/rama/base/head, PR, pruebas y denominadores, evidencia real o sintética, límites, decisión y siguiente acción.
Para un nuevo chat basta: “Continúa AEOS desde docs/control/NEXT_SESSION_HANDOFF.md en Franchute10/autonomous-agent-economy; verifica GitHub y ejecuta la siguiente tarjeta con presupuesto incremental USD 0”.
