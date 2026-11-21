# Plan de ejecución para Luna — AEOS
Fecha: 2026-11-21, America/Lima. Autoría de revisión: Astra.
Estado original: planificación. Actualización 2026-11-21: el propietario autorizó ejecución con Astra; ver [bitácora](ASTRA_EXECUTION_2026-11-21.md). El alcance de las tarjetas sigue vigente; el modelo ejecutor no es una restricción. NEXT_SESSION_HANDOFF.md determina la siguiente acción.

## Diagnóstico de dirección
Hay código de diagnóstico, contratos de agentes y un motor de descubrimiento/evaluación. Aún falta demostrar el recorrido comercial que el propietario quiere. El riesgo principal es encontrar suficientes solicitudes útiles, no producir más informes.
La revisión observó en el motor dependencia directa de Tavily y tres tipos de consulta al mismo índice: web, Facebook y Nextdoor. No hay tres conectores independientes. La beta actual no integra automáticamente ese motor.
El Fix Pack y los documentos anteriores de mercado/Porter no son equivalentes a la nueva prioridad de paquetes de oportunidades. No construir las tres ofertas en paralelo.

## Resultado mínimo y condiciones
Un negocio real entiende el diagnóstico, puede usar un prompt de corrección y recibe un pequeño conjunto de oportunidades que reconoce como pertinente, con evidencia y vía pública de respuesta. El primer piloto puede incluir revisión humana explícita; medir sus minutos y no llamarlo automatización completa.
El diseño admite distintos rubros. La primera evaluación cubre un negocio de productos y dos de servicios para detectar sesgos; no demuestra cobertura universal. Seleccionar el primer segmento comercial por resultado y acceso a usuarios, no por el volumen de código histórico de limpieza.
USD 0 de gasto incremental. Un proveedor configurado o una cuota gratuita histórica no prueba que hoy pueda usarse sin coste: verificar saldo, límite y ausencia de recarga antes de llamadas. Si no puede verificarse, no llamarlo.
Un fallo de acceso no prueba ausencia de demanda. Un resultado de buscador no prueba intención ni fecha; un buen ajuste B2B no equivale a solicitud activa de compra.

## Orden y puntos de decisión
LUNA-001 → LUNA-002 → LUNA-003 → LUNA-004 → LUNA-005.
LUNA-002 decide si merece la pena integrar y vender. La reconciliación restante del equipo sigue en AEOS #4 y no bloquea pruebas sobre copias aisladas verificadas.
No invertir catorce días de búsquedas a ciegas: comenzar con una exploración manual acotada y después hasta tres corridas comparables de la fuente elegida. Si no aporta solicitudes útiles, registrar causas y cambiar una hipótesis de fuente/segmento; no añadir filtros sin analizar originales.
Las tarjetas 003–005 son condicionales. Para habilitarlas, enlazar evidencia de salida de la anterior y crear una subtask concreta en #38 antes de editar. No habilitar producción, pagos reales ni contacto automático por inferencia.

## LUNA-001 — Diagnóstico de productos y servicios con acceso real
**Registro:** AEOS #38. **Estado:** completada a nivel de servicio/HTML acotado el 2026-11-21. Dos sitios reales leídos; corrección #45 integrada; CI 953 passed / 12 skipped. Evidencia y límites en [bitácora](ASTRA_EXECUTION_2026-11-21.md). No acredita DOM, ingesta Google Business, UI ni ventas. Siguiente tarjeta: LUNA-002.
**Base:** AEOS codex/aeos-live-003c; última integración revisada de2d211bc22cbbbe72b615e7434e649feca1b730. Resolver SHA actual; si cambió, revisar diferencia pertinente.
**Leer:** AGENTS.md, PROJECT_HANDBOOK.md, docs/runbooks/aeos-public-beta.md; src/aeos/live/public_beta.py; src/aeos/live/adapters/website_inspector.py; tests/unit/application/live/test_multisector_product_entry.py; tests/integration/live/test_public_beta_web.py.

**Ejecutar:**
1. Confirmar repo/rama/SHA y usar copia aislada; verificar intérprete, dependencias y DNS/HTTPS una vez. No sustituir una corrida del programa por leer la página en un buscador.
2. Seleccionar dos URLs correctas y públicas de negocios ya compartidos, una de productos y otra de servicios. Registrar URL, categoría, alcance y momento de captura. No inventar la dirección si no está disponible.
3. Ejecutar el punto de entrada existente con el mismo presupuesto de rastreo de la beta; conservar la respuesta y revisar manualmente sus hallazgos contra el HTML recuperado.
4. Comprobar metadatos/robots/sitemap dentro de lo que implemente el inspector; distinguir inspeccionado, no disponible e inconcluso. No exigir que un sitio correcto produzca hallazgos.
5. Cuando haya un hallazgo sustentado, comprobar que el prompt contiene solo evidencia observada y acciones realizables. La ausencia de hallazgos no habilita inventar una corrección.
6. Google Business: comprobar la salida honesta de evidencia requerida. Inspección completa solo si hay fuente autorizada; no bloquear la prueba de sitios por esta dependencia.

**Cierre:** dos informes reales revisados, o bloqueo identificado por sitio; URLs y cobertura atribuibles, cero afirmaciones sin evidencia; resultado en #38 y handoff actualizado. Distinguir prueba CLI/servicio de prueba HTTP/UI si no se hicieron ambas.
**Si falla el entorno:** tras una comprobación de DNS/dependencias y una alternativa disponible, registrar BLOCKED con reproducción mínima. Preparar el comando para un entorno existente capaz, sin comprar hosting; avanzar únicamente a la exploración documental/manual de LUNA-002, sin declararla integración automatizada.
**Código:** solo si aparece un defecto concreto: reproducción, corrección pequeña, pruebas focales y controles exigidos por el repo. No reejecutar suites por haber escrito documentación.

## LUNA-002 — Decidir si existe una oferta de oportunidades útil
**Registro:** commercial-lead-engine #4. **Base de evaluación:** codex/intent-evidence-evaluation, SHA revisado a647263bcde2be074479321928b0cd74fc1c0252; confirmar estado actual.
**Leer:** docs/intent-evaluation.md, application/intent_discovery.py, application/intent_evaluation.py, infrastructure/public_search.py y PR #1/#2. Su pila sigue abierta: #2 depende de #1. Se puede evaluar la rama sin fusionar toda la pila.

**Contrato de oportunidad propuesto:**
- URL original accesible y evidencia de una necesidad explícita.
- Fecha original/estado vigente verificable y antigüedad adecuada al tipo de compra; definir ventana antes de buscar.
- Coincidencia de producto/servicio, zona y capacidad del negocio.
- Ruta legítima para responder o presentar propuesta; no presumir contacto ni respuesta.
- Identidad para deduplicar, fuente, fecha de observación, motivo de ajuste y estado de revisión.
Todo campo desconocido queda desconocido; solo lo que cumpla el contrato puede formar parte del paquete.

**Experimento:**
1. Fijar tres perfiles (un producto/dos servicios), oferta y exclusiones, zona, idioma y ventana. Solicitar al propietario únicamente el dato que no esté en la evidencia existente.
2. Explorar originales accesibles antes de programar otro adaptador. Comparar una fuente de solicitudes explícitas con otra categoría pública pertinente; directorios sirven como referencia de oferta, no como intención compradora. No prometer acceso a grupos privados ni a portales sin verificar.
3. Congelar consultas, fuente, límite y criterio. La búsqueda manual ayuda a juzgar la fuente, pero no se reporta como éxito del motor.
4. Si existe cuota verificablemente gratuita, ejecutar el mecanismo actual con journal y revisar originales. Si no existe, evaluar la fuente manualmente y dejar la automatización BLOCKED; no contratar ni eludir el bloqueo.
5. Etiquetar todos los candidatos y una muestra definida de descartados: solicitud real, proveedor, empleo, otra zona, obsoleto, no solicitud o incierto. Incluir casos positivos y negativos sin seleccionar solo aciertos.
6. Registrar hits/URLs únicas/candidatos/revisados/solicitudes válidas/útiles para el negocio, errores y descartes; duración, llamadas y gasto. Precisión sobre etiquetados con denominador y cobertura; recall solo respecto de un conjunto manual explícito, nunca del mercado completo.
7. Tras tres corridas comparables sin solicitudes relevantes revisables, cambiar fuente/segmento o pausar. No concluir que no hay mercado ni rebajar la calificación.

**Umbral de decisión propuesto para este piloto (no garantía estadística):** al menos dos oportunidades elegibles por negocio evaluado y confirmación de utilidad por su responsable; repetir la captura en otra fecha para observar disponibilidad. Si solo un segmento lo logra, limitar la primera oferta a ese segmento y mantener el diseño general. Si solo hay coincidencia B2B sin solicitud, no sustituirla silenciosamente por leads; presentar una oferta distinta para decisión.
**Cierre:** matriz por perfil/fuente con evidencia resumida y decisión CONTINUAR / CAMBIAR FUENTE / PAUSAR. No publicar los journals ni datos personales. Ninguna búsqueda/contacto automático adicional.
**Regresión pendiente:** conservar pruebas de envejecimiento y evidencia real observada bajo los contratos actuales; no copiar fixtures antiguos ni tratar tests sintéticos como cobertura comercial.

### Actualización ASTRA-SOURCE-002 — 2026-11-21
Consulta manual, no ejecución de Tavily: en tres perfiles se hallaron solicitudes públicas, pero ninguna pudo calificarse como oportunidad actual y útil. Para materiales, una solicitud de 8,000 ladrillos en Madre de Dios ya figuraba declarada nula y fuera de zona. Para transporte, una solicitud de traslado de maquinaria en Apurímac cerró el 17/11; el TDR exacto no fue verificado. Para Lumen, una solicitud vigente de modelación estructural no corresponde a consultoría comercial.
Workana devolvió proyectos de servicios explícitos, pero los términos oficiales limitan la extracción/minería y la reventa de su contenido; queda EXCLUIDA del feed AEOS salvo permiso escrito. No se guardan publicaciones individuales. Ver [bitácora ASTRA-SOURCE-002](ASTRA_EXECUTION_2026-11-21.md).
Decisión: LUNA-002 sigue IN_PROGRESS. Próximo incremento: fuente primaria permitida por perfil, estado/fecha verificables y coste USD 0; sin contacto ni integración hasta acreditar utilidad. Esta muestra no mide cobertura del mercado.

## LUNA-003 — Conectar únicamente el recorrido que pasó la evaluación
**Precondición:** 001 funcional y 002 con segmento/fuente viable. Abrir subtask bajo AEOS #38 y revisar el contrato antes de implementarlo.
**Diseño propuesto:** mantener dos repositorios; una interfaz de aplicación intercambia perfil confirmado y oportunidades con evidencia. No fusionar dominios ni crear un runtime general de agentes.
Entrada mínima: business_id, oferta/capacidad, zona, idioma, fuentes autorizadas y presupuesto. Salida: run_id, estado (completo/parcial/bloqueado), oportunidades, procedencia, tiempos/coste y causas de rechazo. Son campos conceptuales; mapear a entidades existentes antes de introducir otras.
Flujo UI: URL → diagnóstico → confirmación de oferta/zona solo si son inciertas → disponibilidad real y muestra limitada → oferta exacta. No exponer por completo el paquete antes de la compra ni inventar un teaser.
Estados de producto deben distinguir procesando, disponible, sin oportunidades y error de acceso. Una lista vacía válida no es fallo técnico.
**Pruebas:** entrada de productos y servicios, información faltante, aislamiento entre negocios, duplicados, cero resultados, fuente caída/parcial, presupuesto agotado, recuperación de ejecución. Revisión de muestras reales aparte.
**Integración de ramas:** revisar motor #1 antes de #2 y migraciones sobre copia de prueba; revisar LIVE contra main por alcance. Resolver conflictos con preservación de datos, no con integración global a ciegas. Tests del SHA final según instrucciones de cada repo.
**Cierre:** recorrido reproducible diagnóstico → perfil → búsqueda → evidencia disponible, sin pago ni outreach.

## LUNA-004 — Oferta y entrega Sandbox del resultado comprado
**Precondición:** disponibilidad demostrada y oferta concreta fijada; subtask bajo #38.
Preservar el diagnóstico y prompt gratuitos. Fix Pack no se convierte automáticamente en SKU de leads. Revisar AEOS #2 (alineación de alcance) sobre LIVE actual; #1 contiene una implementación Stripe anterior y sigue draft. Comparar y decidir su destino en una tarea separada, sin mezclar proveedores ni cerrar trabajo sin revisión.
**Invariante de diseño:** generar y persistir un resultado inmutable antes de ofrecerlo; asociar orden a negocio, resultado, versión/hash, producto, precio y cantidad. La entrega recupera ese resultado, no repite diagnóstico/búsqueda para reconstruir lo comprado.
Definir vigencia y disponibilidad antes del checkout; con inventario insuficiente ofrecer únicamente una cantidad concreta validada o no vender. No prometer exclusividad salvo que exista reserva que la garantice.
La persistencia elegida debe sobrevivir al reinicio/despliegue del host existente; comprobar su capacidad sin asumir que almacenamiento gratuito es durable. Si no hay persistencia adecuada sin coste, bloquear checkout y conservar el piloto gratuito.
**Aceptación:** resultado idéntico tras pago y reinicio; webhook/reintento duplicado sin doble efecto; autenticación y aislamiento; importe/producto/moneda/orden validados en servidor; pago pendiente/fallido y recuperación; paquete ausente/expirado; evento de navegador no autoriza entrega. Sandbox completo documentado, sin cargos reales.
**Cierre:** evidencia de extremo a extremo y decisión explícita sobre lo que falta para producción. Una compra Sandbox no acredita disposición a pagar.

## LUNA-005 — Piloto con tres negocios
**Precondición:** evidencia de utilidad y entrega estable. No enviar invitaciones sin instrucción de contactar.
Tres responsables prueban URL → informe → oportunidades → siguiente acción. Medir si entienden el informe sin explicación, si pueden usar la corrección y por qué cada oportunidad les sirve o no. No exigir tres sectores si 002 solo habilitó uno; registrar ese alcance.
Precio/cantidad son experimentales. Separar intención declarada, prueba Sandbox, compra real y resultado comercial posterior. Registrar minutos humanos, coste operativo incremental y margen estimado por entrega; USD 0 de proveedor no significa tiempo gratuito ni rentabilidad.
Cargos reales/despliegue Live requieren decisión específica posterior. Agensi/LinkedIn/X se evalúan como distribución cuando exista una demostración y una oferta; no construir ahora un skill genérico ni contar visitantes declarados de una plataforma como compradores.

## Estimación y disciplina de continuidad
No hay base para prometer que todo esté listo en 2–3 semanas. Esa ventana puede ser una meta de piloto condicionada a 001/002; estimar calendario después de medir acceso, rendimiento de fuente y tamaño real de integración.
Corte 2026-11-21: 001 se ejecutó desde GitHub Actions; siguiente bloque del modelo disponible: LUNA-002, fichas concretas y evaluación comparable de fuentes. No convertirlo en otro proyecto de semanas antes de mirar originales.
Antes de pausar o cerrar cada bloque, guardar en el issue: ID/estado, base y head, PR, pruebas realmente ejecutadas, resultado real o fixture, límites, decisión y siguiente paso. Si cambia la siguiente tarea, actualizar NEXT_SESSION_HANDOFF.md.
No depender de detectar que el chat está por llenarse: cada bloque deja checkpoint. Conservar historial de decisiones fechado; no duplicar conversaciones completas ni crear múltiples documentos llamados estado actual.

## Prompt de arranque
“Lee docs/control/NEXT_SESSION_HANDOFF.md y docs/control/LUNA_EXECUTION_PLAN.md en Franchute10/autonomous-agent-economy. Verifica GitHub y las instrucciones del repositorio. Ejecuta la siguiente tarjeta habilitada; conserva el presupuesto incremental de USD 0 y registra resultado y siguiente acción en GitHub antes de terminar. No reconstruyas los chats ni declares capacidades sin evidencia.”
