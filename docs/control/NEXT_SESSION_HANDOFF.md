# AEOS — Punto de continuidad

**Actualizado:** 2026-11-21 (America/Lima)  
**Fuentes canónicas:** este documento, el [plan de control](PROJECT_CONTROL.md), los [issues de AEOS](https://github.com/Franchute10/autonomous-agent-economy/issues) y el [issue de calidad de leads](https://github.com/Franchute10/commercial-lead-engine/issues/4).

## Cómo retomar sin reconstruir el chat

1. Leer este handoff.
2. Verificar el estado actual de GitHub y continuar con los issues enlazados; este documento puede quedar desactualizado.
3. Leer PROJECT_CONTROL.md para prioridades. Consultar PROJECT_READINESS.md y el ledger de validación solo para detalles históricos o técnicos necesarios.
4. No pedir a Frank que vuelva a resumir los chats ni repetir trabajo ya registrado. Preguntar solo por un dato que realmente falte para la tarea concreta.

Este handoff reemplaza el chat como memoria operativa. Los chats previos aportan contexto histórico; GitHub es la fuente del estado, decisiones, código y pruebas.

## Objetivo vigente

AEOS mantiene su tesis de una organización gobernada de agentes, con objetivos, roles, presupuesto, evidencia, autorizaciones y aprendizaje. La prioridad comercial es probar un flujo simple para negocios de productos y servicios:

**URL o Google Business → diagnóstico gratuito con evidencia y prompt de corrección → posible oferta de oportunidades comerciales útiles.**

Los importes objetivo de USD 5 por 2–3 oportunidades y USD 10 por 5–6 son hipótesis. No vender leads como verificados, no limitar el producto a limpieza y no convertir una auditoría genérica de LLM en el producto.

## Estado verificado al 2026-11-21

- **AEOS main:** PR #40 integró el plan de control y el ledger de validación; merge 963491a9d8f45b107c95835e097a03d2b6636a89.
- **AEOS LIVE:** PR #39 integró la selección de páginas de productos/catálogos/ofertas; merge f5cf0c642e36f7a493a48908164c5aba0798dc99, sobre base 0cc8598. CI reportó 941 pruebas aprobadas y 12 omitidas; Ruff, formato, mypy y diff check pasaron.
- **Revisión de parches:** las 34 diferencias semánticas del parche aeos-main-source-tests fueron revisadas. Se conserva LIVE; no reaplicar los parches antiguos. También se recuperó y comparó el blob 2555b33 de real_lead_pilot.py; LIVE exige organization_id para almacenamiento predeterminado de perfiles reales y separa el espacio sintético.
- **Prueba adicional de esta sesión:** los cuatro casos sintéticos (tienda de herramientas, juguetería, consultoría y HVAC) pasaron en un harness Python directo; git diff --check pasó. No se pudo ejecutar pytest en este runner porque no está instalado y no había acceso al registro de paquetes.
- **Prueba real:** el diagnóstico del sitio público de Lumen falló en dns_resolution antes de leer robots.txt. Es una limitación de red del runner, no evidencia de que el sitio esté mal. No hay leads reales validados, búsqueda live repetible, pagos ni disposición a pagar demostrada.
- **Google Business:** no afirmar que el perfil fue inspeccionado sin fuente autorizada o evidencia del propietario.

Los detalles están registrados en [AEOS-PRODUCT-001 (#38)](https://github.com/Franchute10/autonomous-agent-economy/issues/38), [AEOS-OPS-001 (#4)](https://github.com/Franchute10/autonomous-agent-economy/issues/4) y [LEADS-VAL-001 (#4)](https://github.com/Franchute10/commercial-lead-engine/issues/4).

## Próxima tarea concreta

**PRODUCT-001 — diagnóstico real en staging con salida DNS/HTTP pública.**

1. Usar un sitio público permitido de un negocio de productos y otro de servicios, de preferencia ya compartidos por Frank; verificar que las URLs actuales sean correctas.
2. Ejecutar el diagnóstico y guardar evidencia anonimizada de páginas recibidas, robots, sitemap, metadatos, hallazgos y prompts. Respetar robots, límites de rastreo y políticas del sitio.
3. Distinguir error de red del resultado del diagnóstico; no evaluar una web si no se pudo recuperar.
4. Registrar resultado en #38. Google Business solo con evidencia autorizada.
5. Después, ejecutar LEADS-VAL-001 por separado: una vertical de productos y dos de servicios, fuente permitida, muestra etiquetada por persona y costo adicional objetivo de USD 0. No suavizar criterios para inflar resultados.
6. Revisar cobro/entrega en PRs AEOS #1/#2 únicamente después de verificar su base, head, CI y comportamiento actual. Mantener Sandbox y no activar cobros.

Esta tarea requiere un entorno con DNS y salida web real. Si el siguiente runner tampoco tiene esa salida, documentar el bloqueo y avanzar la evaluación offline o una tarea independiente, sin repetir intentos ciegos.

## Pendientes separados

- **Laptop Windows:** el inventario disponible es del 2026-11-20 y solo registra nombres/estados; no inspecciona contenidos ignorados ni completa el escaneo de secretos/historial. Hace falta una captura actual desde esa laptop. Hasta entonces, preservar sus worktrees, datos privados y respaldos; no hacer reset, clean, restore, pull ni staging masivo.
- **Motor de leads:** PRs #1/#2 siguen sujetos a revisión e integración en orden. No asumir que el checkout local está sincronizado ni usar una clave compartida previamente en el chat.
- **Código:** la copia de trabajo de esta sesión puede estar atrasada en 0cc8598 con el diff de PR #39 presente sin commit. GitHub en f5cf0c6 es la referencia; iniciar cambios de código desde una rama limpia y confirmar SHA/estado primero.

## Regla de continuidad

Al cerrar cada tarea, actualizar el issue correspondiente con resultado, SHA/PR, pruebas y límites; actualizar este handoff solo si cambia la siguiente acción o el estado global. Mantener una sola siguiente acción principal. No dejar decisiones ni progreso exclusivamente en el chat.
