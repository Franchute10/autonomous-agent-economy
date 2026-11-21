# Bitácora Astra — ejecución y decisión de fuentes
Fecha de revisión: 2026-11-21 (America/Lima).
Estado: soporte de productos integrado en LIVE; diagnóstico de dos sitios reales ejecutado; corrección de muestreo y prompt integrada en LIVE mediante PR #45; producto comercial aún no validado.
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
La ejecución local no pudo correr pytest completo, Ruff ni mypy por módulos ausentes. Se resolvió esa dependencia mediante GitHub CI sobre el head final: 949 passed / 12 skipped; lint, formato y mypy aprobados. Evidencia: https://github.com/Franchute10/autonomous-agent-economy/actions/runs/44919384588 . Las primeras consultas vacías no se trataron como éxito; se revisaron después el job y su log.
**Decisión ejecutada:** PR #42 integrado en codex/aeos-live-003c, merge 548ed0c23fddf1642b26f49aae128c7ae17a2638. Esta corrección no demuestra que todos los formularios/pilotos admitan negocios solo de productos; el preview específico de procurement todavía se apoya en primary_services y no se amplía en este cambio.

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
- Electrodomésticos: https://www.sutran.gob.pe/wp-content/uploads/2026/11/05.-EETT-Electrodom%C3%A9sticos-2026-VF-F-.pdf
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

## 6. RUNNER-001 y LUNA-001 — prueba real completada a nivel de servicio
El bloqueo local de DNS no era una incapacidad del programa. Se usó GitHub Actions estándar del repositorio público existente, sin secretos, proveedor de pago, artefactos persistidos ni programación periódica.

Primera corrida: [PR #44](https://github.com/Franchute10/autonomous-agent-economy/pull/44), head e58f58bd988bfd9d7ad1383ae13b95282695fce0, [run 44955224788](https://github.com/Franchute10/autonomous-agent-economy/actions/runs/44955224788), 2026-11-21 17:09 Lima. Ambos sitios: SUCCEEDED, 3 páginas recibidas. El PR #44 se cerró como experimento completado y reemplazado por #45; no se integró separadamente.

La muestra inicial de Lumen incluyó dos variantes de /contact con parámetros de botón y produjo títulos repetidos. Esto no prueba que ambas páginas sean idénticas ni que todos los duplicados sean falsos: la meta description también coincidía con la portada.

### ASTRA-CRAWL-004 — corrección focal
[PR #45](https://github.com/Franchute10/autonomous-agent-economy/pull/45), base LIVE 548ed0c23fddf1642b26f49aae128c7ae17a2638:
- Prioriza rutas distintas antes de variantes de consulta, conservando las URLs originales. No elimina parámetros ni equipara automáticamente dos contenidos.
- El prompt público español/inglés exige comparar contenido y cambiar metadatos solo cuando esté justificado, consistente con la recomendación interna.
- Cuatro pruebas sintéticas verifican que contacto no desplace productos, que productos identificados por query sigan disponibles, que se conserve prioridad entre rutas distintas y que ambos idiomas condicionen la corrección.
- Pruebas focales locales: 4/4. Primera CI detectó formato del fixture, corregido; no se tomó ese run como aprobado.

Segunda corrida real: head 60aca905c612586d9800c16acb310202090d3565, [run 44955755471](https://github.com/Franchute10/autonomous-agent-economy/actions/runs/44955755471), 2026-11-21 17:15 Lima.

| Negocio / URL pública | Resultado real | Interpretación y límite |
|---|---|---|
| Productos: https://mega-ceramicos-propuesta.vercel.app/ | SUCCEEDED; 3 páginas; 0 hallazgos confirmados; H1 pendiente | No se inventa un defecto; HTML limitado no certifica sitio correcto ni ausencia de errores |
| Servicios: https://lumen.frank-2e.workers.dev/ | SUCCEEDED; 3 páginas; meta description repetida en portada, /contact y /about | Ya no ocupa dos cupos con contacto. Prompt con las 3 URLs y comparación previa; no afirma pérdida de posiciones |

Se revisaron los extractos y prompts emitidos por el programa; no hubo auditoría manual exhaustiva de todo el HTML ni DOM renderizado. Presupuesto de la beta: 3 páginas, 500 KB por respuesta, 2 s por solicitud y 25 s totales de HTTP; alarma exterior de 70 s por sitio. No extrapolar este muestreo a indexación completa, experiencia UI o ventas.

Google Business se comprobó localmente con URL sintética: OWNER_EVIDENCE_REQUIRED, 0 páginas, sin hallazgos, Fix Pack no disponible. Es una prueba del manejo honesto de entrada, no una inspección de un perfil real ni implementación de su ingesta autorizada.

Las dos corridas son del servicio Python real. No son dos corridas de generación de leads. Cero llamadas de API de pago; ningún contacto ni cobro.

### Cierre técnico de PR #45
Head final: 4da8986baf48f389265ac542715bf5f5f14f1c83. [CI 44955889071](https://github.com/Franchute10/autonomous-agent-economy/actions/runs/44955889071): 953 passed / 12 skipped; Ruff, formato y mypy aprobados. Entre el smoke y este head solo cambió el formato/nombre de una prueba, no los blobs de producción ni workflow. Diff remoto de cuatro archivos revisado.
**Decisión ejecutada:** PR #45 integrado en codex/aeos-live-003c, merge de2d211bc22cbbbe72b615e7434e649feca1b730. No es release ni integración de LIVE a main. PR #44 cerrado como experimento sustituido. LUNA-001 queda completado en su alcance de servicio/HTML acotado; la ingesta autorizada de Google Business, DOM y validación UI/comercial siguen sin acreditarse.

## 7. Próximo bloque — LUNA-002
El siguiente cuello de botella es comprobar utilidad comercial. No volver a ejecutar RUNNER-001 ni la suite solo por actualizar documentos.
1. Partir de los negocios ya suministrados, con una ficha de producto y dos de servicios; conservar como desconocidas las capacidades que no estén confirmadas.
2. Fijar oferta, zona, idioma, ventana de antigüedad y exclusiones antes de buscar. No presentar los tres pliegos de esta bitácora como leads para Mega Cerámicos o Lumen: no se confirmó su ajuste.
3. Revisar solicitudes originales y estado vigente en una fuente pertinente por perfil. Registrar consultas y denominadores, sin confundir la investigación documental con una ejecución del motor.
4. Preparar muestra privada únicamente con candidatos elegibles; pedir la valoración del responsable sobre esa muestra concreta. Sin utilidad confirmada, no habilitar compra.
5. Registrar en Motor #4 y actualizar NEXT_SESSION_HANDOFF.md. Cambiar hipótesis tras tres corridas comparables sin rendimiento; las tarjetas 003–005 siguen condicionadas.


## 8. ASTRA-SOURCE-002 — muestra de solicitudes y permisos de fuente (2026-11-21)

**Propósito:** identificar si una fuente pública entrega solicitudes actuales para perfiles ya presentes en el ecosistema: materiales de construcción (Mega Cerámicos), transporte de carga especial (AC Moreno) y consultoría comercial (Lumen). No se asumió capacidad, zona de servicio o acreditación no confirmada.

**Método y alcance:** exploración manual acotada mediante consultas en español y lectura de páginas fuente disponibles, con observación al 21/11/2026. No se llamó al motor de Tavily ni a una API de pago, no se extrajeron datos de usuarios ni se contactó a nadie. Esta muestra no es una corrida automatizada, comparación de motores, medida de cobertura ni cálculo de precisión/recall. Las páginas individuales de GOREMAD agotaron el tiempo de apertura; sus detalles siguientes provienen de la versión indexada por el buscador y requieren reabrir en el portal antes de actuar.

| Perfil | Solicitud pública encontrada | Evaluación al 21/11 |
|---|---|---|
| Materiales de construcción | GOREMAD, solicitud 6418: 8,000 ladrillos King Kong 18 huecos para obra Boca Colorado. Fecha 6–9/11; el resultado indexado informa que se declaró nula el 11/11 por precios por encima del presupuesto y que se haría una nueva convocatoria. | Solicitud real pero vencida/nula, en Madre de Dios, fuera de la cobertura norte atribuida al distribuidor; no es lead vigente. Fuente: https://cotizaciones.regionmadrededios.gob.pe/solicitud/21860 . Reapertura directa no disponible en esta sesión. |
| Transporte de maquinaria | DRTC Apurímac, cotización 467: movilización y desmovilización de maquinaria; publicada 16/11, cierre 17/11 a las 08:00. La entidad exige RNP, ficha/consulta RUC y recepción por su canal dentro del plazo. | Solicitud real y pertinente por categoría, pero vencida antes de la observación; el TDR/enrutamiento exacto no se verificó, así que no se califica capacidad. Fuente primaria accesible: https://drtcapurimac.gob.pe/portal/cotizacion-n467-servicio-de-movilizacion-y-desmovilizacion-de-maquinarias/ . |
| Consultoría comercial | GOREMAD, solicitud 6556: cálculo y modelación estructural; publicada 20/11, límite 23/11 a las 12:00. | Aún en plazo al momento de la observación, pero es ingeniería/modelación estructural, no consultoría comercial/RevOps; descartar por especialidad. Detalle indexado: https://cotizaciones.regionmadrededios.gob.pe/solicitud/21999 . Apertura directa no disponible. |

La ayuda del portal GOREMAD explica que muestra solicitudes vigentes por defecto y permite filtrar por estado/fechas; https://cotizaciones.regionmadrededios.gob.pe/ayuda . Aun así, lo hallado no valida este portal como canal universal: depende de geografía, RNP, requisitos del postor y tiempo corto de respuesta.

### Fuente de servicios freelance — Workana, EXCLUIDA para el feed AEOS
Una búsqueda exploratoria encontró páginas de proyectos explícitos de consultoría/ventas con señales de estado mezcladas entre encabezado y descripción. Al revisar las condiciones oficiales en español, los términos limitan el contenido a uso personal/no comercial y prohíben extraer, indexar o hacer minería de datos (incluidos procesos manuales o automáticos), además de reproducir o revender contenido. Ver https://help.workana.com/hc/es/articles/360041499974-T%C3%89RMINOS-Y-CONDICIONES-DE-WORKANA (secciones de licencia/restricciones).

**Decisión:** no incorporar Workana como fuente de AEOS ni reproducir sus publicaciones en una muestra pagada, a menos que exista permiso escrito que lo autorice. Un freelancer puede considerar Workana como canal propio usando su cuenta y las funciones oficiales, por separado del feed de AEOS. Por respeto a los términos y a los usuarios, esta bitácora no copia títulos, nombres, texto ni URLs de proyectos individuales.

### Resultado de ASTRA-SOURCE-002
- Cero oportunidades actuales calificadas para los perfiles probados.
- Una fuente oficial de compras muestra solicitudes explícitas pero devuelve obsoletas, fuera de zona o con especialidad no coincidente en esta muestra acotada.
- Un marketplace de servicios tuvo señales de intención, pero queda excluido de extracción/reventa por sus términos.
- La búsqueda web genérica también devuelve directorios, páginas de proveedores y puestos laborales; esos elementos no son solicitudes compradoras.
- No se presentó paquete al dueño para juicio de utilidad porque no quedó candidato elegible. No se habilita integración, precio ni cobro.

**Siguiente paso:** seleccionar una fuente permitida por perfil, confirmar sus términos/licencia, cobertura geográfica, fecha/estado original y ruta de respuesta antes de automatizar. Priorizar canales oficiales de solicitudes y datos suministrados por el dueño con permiso; mantener la automatización en BLOCKED si no se demuestra acceso autorizado y gratuito. No concluir que el mercado carece de demanda a partir de esta muestra.


## 9. Corrección de alcance del piloto — 2026-11-21

En la conversación AEOS original, el propietario definió como empresas piloto en Estados Unidos a **Construction Nation Group** (el propietario la refiere como Dallas; el sitio consultado y los informes históricos indican DFW/Plano) y **CMIMBELA Cleaning LLC** (Sarasota). El dictado “Seminvela” parece referirse a CMIMBELA; no reemplazar el nombre del sitio. El propietario también escribió “Nation Construction”; los informes y el sitio dicen Construction Nation Group. Confirmar la denominación antes de materiales externos.

La selección posterior de Mega Cerámicos, AC Moreno y Lumen, y la búsqueda en GOREMAD/DRTC/OECE/SEACE, fue una desviación del piloto solicitado. Se conserva como investigación peruana independiente, pero no se debe usar para aceptar o rechazar la hipótesis estadounidense, calcular yield o decidir el producto. Workana/LinkedIn tampoco quedan elegidos para la búsqueda de EE. UU.; LinkedIn sigue pendiente de decisión. No hubo autorización de contacto.

Los informes de smoke de 2026-11-21 de Mega Cerámicos y Lumen prueban una ejecución técnica del servicio de diagnóstico en esos sitios, pero no de los sitios/mercados de las dos empresas piloto. Los informes históricos del 2026-11-10 sí nombran https://constructionnationgroup.com/ y https://cmimbelacleaningllc.com/; deben tratarse como evidencia de ese momento y versión, no como prueba automática de la revisión #45 ni del actual generador de leads. El siguiente bloque debe retomar los dos perfiles estadounidenses, hallar fuentes con acceso permitido a coste USD 0 y evaluar solicitudes originales por separado.
