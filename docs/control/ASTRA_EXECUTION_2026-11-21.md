# Bitácora Astra — ejecución y decisión de fuentes
Fecha de revisión: 2026-11-21 (America/Lima).
Estado: corrección focal implementada en PR draft; exploración externa ejecutada; producto comercial aún no validado.
Solicitud del propietario: aprovechar Astra también para ejecutar y eliminar bloqueos. Actualiza la separación anterior que reservaba toda implementación para Luna.

## 1. Resultado concreto de código — ASTRA-PRODUCT-003
Revisión estática y reproducción detectaron dos restricciones:
- BusinessProfile rechazaba primary_services vacío aunque hubiera products.
- El ajuste de oportunidades solo comparaba servicios principales/secundarios; ignoraba el catálogo.

[PR #42](https://github.com/Franchute10/autonomous-agent-economy/pull/42) permite perfiles con catálogo explícito sin servicios e incorpora products al ajuste de oferta. Mantiene la oferta conocida vacía como inválida y conserva controles de evidencia, zona y cierre.
Head revisado: 7d1a2dfc0f16a338cb76b06e3e350429641b1c44. Base remota: f5cf0c642e36f7a493a48908164c5aba0798dc99, rama LIVE.
Archivos: src/aeos/live/domain/profile.py; src/aeos/live/domain/opportunity_inbox.py; tests/unit/application/live/test_product_opportunity_fit.py.

### Prueba ejecutada
Python 3.12.14, worktree aislado en 0cc8598. Los dos blobs de dominio coincidían exactamente con LIVE remoto:
- profile.py: 841fcda80e56a9db0497cb286e87c0d8ce703f33.
- opportunity_inbox.py: 62f77b1ccb00854f67a617af3d58be833710da5e.
Comparación remota 0cc8598→f5cf0c6: solo selector web y su prueba (PR #39), fuera de los imports de esta prueba.
Comando reproducible, desde el checkout del PR:
```bash
PYTHONPATH=src python -m unittest discover -s tests/unit/application/live -p test_product_opportunity_fit.py -v
```
Windows PowerShell: establecer $env:PYTHONPATH="src" y ejecutar el mismo comando python sin el prefijo de variable.
Antes: 8 casos, 6 aprobados / 1 fallo / 1 error. Después: 8/8 aprobados; git diff --check aprobado.
Casos: producto único, negocio mixto, producto distinto, zona distinta, solicitud cerrada, sintético no calificable como real, servicio existente y oferta vacía inválida.
No se ejecutaron pytest completo, Ruff ni mypy: módulos ausentes; no convertir ese bloqueo en PASS. Las consultas de workflows/statuses del head inicial devolvieron listas vacías, no éxito.
**Decisión:** PR draft, no integrar hasta controles completos sobre el head final. Esta corrección no demuestra que todos los formularios/pilotos admitan negocios solo de productos; el preview específico de procurement todavía se apoya en primary_services y no se amplía en este cambio.

## 2. Comprobación del entorno
Se comprobó DNS para el sitio de consultoría y el portal de contratación: ambos fallaron con resolución temporal. No se repitieron llamadas ciegas ni se contrató infraestructura.
La búsqueda/lectura externa mediante el servicio de investigación sí pudo consultar fuentes públicas. Son dos rutas distintas: leer originales desde investigación NO demuestra que el programa AEOS pueda recuperarlos.
No se ejecutó Tavily, no se activó pago, no hubo contacto con compradores. No se contrató ningún proveedor ni se incurrió en gasto adicional de API.

## 3. Experimento de fuentes — ASTRA-SOURCE-001
Método: descubrimiento por buscador, apertura del original y lectura de tres pliegos. Muestra intencional pequeña, elegida para explorar límites; no aleatoria, no benchmark de precisión/recall. Se revisaron seis unidades de decisión, sin atribuirlas a negocios reales.

| Caso | Evidencia observada al revisar | Decisión |
|---|---|---|
| Productos: electrodomésticos, SUTRAN | Índice con cierre 23/11/2026; pliego identifica ocho hervidores y seis cafeteras, entrega en Lima y experiencia requerida | Candidato documental; falta perfil capaz, confirmación de disponibilidad y revisión del dueño |
| Servicios TI: switches, SUTRAN | Cierre publicado 23/11/2026; pliego exige experiencia y capacidades técnicas | Candidato documental; no califica para consultoría comercial genérica |
| Servicios técnicos: enfriamiento de data center, SUTRAN | Cierre publicado 23/11/2026; exige canal autorizado del fabricante y especialistas | Candidato documental condicionado; no equivale a HVAC residencial |
| Asistencia administrativa, DRTC Apurímac | Publicado 20/11 y cierre ese mismo día | Excluir por vencimiento al 21/11 |
| Estantería, Hospital Espinar | El buscador mostró convocatoria de noviembre; la apertura devolvió una versión anterior con fechas ya vencidas | Conflicto de versiones; no promover |
| Consultoría comercial/Ads, Workana | Buscador y sección descriptiva sugieren abierto, cabecera original indica Finalizado; fecha de octubre | Estado conflictivo y antigüedad; no promover ni asumir posibilidad de responder |

Resultado de la muestra: 3 candidatos documentales pendientes de ajuste, 1 vencido y 2 conflictos; **0 oportunidades confirmadas como útiles por un negocio, 0 vendibles demostradas**. No es un resultado del motor automatizado. No generalizar una tasa de éxito a partir de estos seis casos.

### Fuentes originales
- Índice SUTRAN: https://www.sutran.gob.pe/contrataciones-de-bienes-y-servicios/
- Electrodomésticos: enlace de especificaciones publicado en la fila correspondiente del índice; se abrió y revisó durante esta sesión.
- Switches: https://www.sutran.gob.pe/wp-content/uploads/2026/11/06.-TDR-MANTENIMIENTO-SWITCHES_V2-F-F-F.pdf
- Enfriamiento: https://www.sutran.gob.pe/wp-content/uploads/2026/11/04-TDR-Mantenimiento-de-Sistema-de-Enfriamiento-de-Data-Center-v7-F-F-1.pdf
- Caso vencido: https://drtcapurimac.gob.pe/portal/cotizacion-n-485-servicio-de-asistencia-tecnica-administrativa/
- Fuente con versiones distintas: https://mail.hospitalespinar.gob.pe/solicitudcotizacion.php
- Caso de estado contradictorio: https://www.workana.com/es/job/consultoria-estrategica-para-optimizar-ventas-en-hotmart-y-facebook-ads

Los cierres y estados deben revisarse nuevamente antes de actuar. La lectura de una página pública no demuestra permiso para extracción masiva o reventa. No se almacenan aquí contactos personales ni documentos completos. Las notas de requisitos describen esos pliegos, no asesoría sobre elegibilidad legal de una empresa.

## 4. Alternativas y elección
La fuente debe seguir al perfil y al tipo de necesidad, no a la historia de un piloto.

| Ruta | Valor potencial | Límite / decisión |
|---|---|---|
| Solicitudes públicas de cotización | Necesidad explícita, plazo, especificaciones; abarca bienes y servicios | Prioridad de experimento para un negocio que pueda cumplir los requisitos; no obligar a todos a vender al Estado |
| Marketplaces de proyectos | Solicitudes de servicios concretas | Probar solo lectura/acceso permitido; comprobar estado y condiciones de respuesta; no construir un scraper ni asumir acceso gratuito |
| Solicitudes directas públicas locales | Potencial para servicios de consumo | El índice actual tiene cobertura incierta; muestrear originales y cambiar de fuente tras corridas sin rendimiento |
| Solicitudes aportadas por dueño o cuenta autorizada | Acceso a necesidades que no aparecen en índices | Reusar captura manual y controles existentes; marcar origen/permiso; no inventar un conector disponible |
| Empresas afines / socios de referencia | Prospectos B2B o posibles alianzas | Conservar en categoría distinta: no venderlos como compradores que solicitaron un producto |
| Agensi | Distribución de una capacidad empaquetada | Posterior a demostrar una función útil; no resuelve por sí solo la obtención de leads |

Comprobación técnica adicional:
- TED documenta búsqueda de anuncios publicados sin autenticación: https://docs.ted.europa.eu/api/latest/search.html . Es una posibilidad de acceso técnico, no una recomendación comercial para un negocio que no opera en ese mercado. No se ejecutó su API.
- SAM.gov exige API key y aplica límites por rol: https://open.gsa.gov/api/get-opportunities-public-api/ . No es un reemplazo anónimo listo para usar; no se ejecutó su API.
- El portal OECE no se pudo verificar suficientemente en esta sesión; no afirmar que su API está integrada o accesible.
- Web/Facebook/Nextdoor actuales siguen siendo consultas a un único índice Tavily. No confundir diversidad de consultas con diversidad de proveedores.

## 5. Qué construir y qué evitar
**Decisión de implementación:** reutilizar captura, tipos de demanda, evidencia y calificación ya existentes. No crear otro motor paralelo. Separar descubrimiento de calificación; normalizar observaciones de cada fuente antes de evaluar.
La selección de fuente debe considerar: oferta concreta, alcance geográfico, tipo de comprador, capacidades y requisitos. Un LLM puede proponer términos o extraer campos; debe aportar evidencia, y la lógica existente debe validar estados y autorización. No se añade otro modelo para ocultar una fuente sin resultados.

Brechas que requieren tarjetas acotadas, no cambios masivos en esta entrega:
1. Puerto tipado de búsqueda en el motor: actualmente application importa Tavily directamente. Cambiar solo al introducir una segunda fuente probada; no abstraer por deporte.
2. Conflictos de fuente: mantener por separado fecha de publicación, fecha de observación y estado. Si dos representaciones discrepan, marcar revisión; el snippet no gana al original.
3. Plazos exactos: Opportunity usa official_deadline de tipo date; evaluar extensión con hora/zona antes de comercializar avisos que vencen el mismo día. No afirmar que este cambio está implementado.
4. Elegibilidad: requisitos de fabricante, experiencia y personal no se deducen de una palabra como HVAC; contrastarlos con perfil autorizado. Conservar incertidumbre.
5. Productos: validar luego el recorrido de entrada/UI/exportación; PR #42 solo cubre contrato y ajuste de oportunidades.

La oferta inicial debe vender utilidad: qué solicitud existe, por qué encaja, qué falta confirmar y cómo responder legítimamente. No prometer exclusividad, compradores confirmados ni un número fijo de oportunidades ausentes.
Medir minutos humanos por entrega. Gasto de API cero no implica negocio rentable. Precio menos costes y comisiones debe cubrir el trabajo necesario; fijar el paquete después del experimento.

## 6. Próximo bloque ejecutable — RUNNER-001
Objetivo: usar un entorno existente capaz para validar PR #42 y ejecutar LUNA-001; no volver a reconstruir chats.
1. Verificar head del PR, checkout aislado e instrucciones; confirmar Python/dependencias, DNS y HTTPS.
2. Ejecutar las ocho regresiones, pytest completo, Ruff check/format y mypy sobre el head final. Si falla, corregir solo la causa y actualizar el PR. Integrar a LIVE únicamente con evidencia suficiente.
3. Ejecutar diagnóstico real de un sitio de productos y otro de servicios; distinguir errores de transporte y resultados del sitio. No sustituirlo por esta investigación web.
4. Continuar LUNA-002 con un perfil real y la ruta adecuada. Para el primer ensayo de productos, confirmar catálogo/capacidad del dueño antes de calificar cualquiera de los candidatos documentales.
5. Actualizar #38, Motor #4 y NEXT_SESSION_HANDOFF.md al completar o bloquear. Las tarjetas de integración y cobro siguen condicionadas a utilidad demostrada.

Si el entorno no permite esos controles, mantener PR draft y registrar la dependencia exacta; no reiniciar ordenamiento general ni comprar un runner. Esta bitácora conserva la reproducción y las decisiones para otro modelo.
