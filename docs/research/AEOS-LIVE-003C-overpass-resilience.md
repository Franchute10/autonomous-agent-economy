# AEOS-LIVE-003C — salida de descubrimiento y resiliencia Overpass

## Resultado

La consola distingue `FAILED`, `UNSUPPORTED`, `COMPLETED_NO_RESULTS` y
`COMPLETED_WITH_RESULTS`. Si la consulta falla, muestra el conteo como no
disponible y conserva como desconocido el estado del mercado. Si el vertical no
tiene mapeo, declara que no se envió ninguna búsqueda. Solo una respuesta
completada puede presentar conteos numéricos.

Los informes y la consola registran el estado final, el proveedor, el número de
intentos, los reintentos y el estado HTTP. El adaptador conserva una sola
solicitud por ejecución y no reintenta respuestas 502/503/504.

## Decisión del proveedor

El endpoint configurado es
`https://maps.mail.ru/osm/tools/overpass/api/interpreter`. La lista pública
de instancias de Overpass de OpenStreetMap todavía lo documentaba el
**2026-11-20** y mostraba la política del operador de permitir proyectos sin un
límite de solicitudes anunciado. Esa política no es una garantía de
disponibilidad. La validación del **2026-11-09** observó HTTP 504 para CMIMBELA
y HZ.

No se agregó reintento automático: aunque 502/503/504 pueden ser transitorios,
repetir una consulta tras una respuesta del servidor aumenta la carga del
servicio compartido, sin garantía de que la segunda llamada funcione. Tampoco se
configuró failover. Las instancias alternativas tienen operadores, límites,
cobertura y términos propios; no se eligió una instancia para este piloto ni se
verificó su política para este uso.

El endpoint puede configurarse con `--overpass-endpoint` o con la variable de
entorno `AEOS_OVERPASS_ENDPOINT` (la opción CLI tiene precedencia). Antes de
usar otra instancia, revisar su endpoint y sus condiciones vigentes en la
[lista pública de instancias Overpass](https://wiki.openstreetmap.org/wiki/Overpass_API#Public_Overpass_API_instances).
La cobertura de una fuente alternativa también debe validarse para cada área
consultada.

## Validación

Las pruebas simulan las cuatro salidas y verifican que un 502, 503 o 504 produce
exactamente un intento. Durante esta revisión documental no se hicieron
solicitudes reales al mercado.
