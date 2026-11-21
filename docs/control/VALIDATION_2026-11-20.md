# Evidencia de validación — 2026-11-20

Entorno aislado Linux, Python 3.12.14. Clones nuevos de GitHub; no se accedió a la laptop. Dependencias instaladas desde pyproject: pytest 8.4.2, Ruff 0.17.6, mypy 1.20.2. No se utilizó una clave de pago.

| Código probado | SHA base | Pytest | Otros controles |
|---|---|---|---|
| AEOS main | a06ce3ffef13e17e4f2aebed5483a89423069b44 | 595 passed, 7 skipped | Suite base; no lint adicional de main |
| AEOS LIVE | 0cc8598e2272f6da25de07826b880d37e7ab43c4 | 937 passed, 12 skipped | Ruff check/format y mypy: PASS |
| Motor main | e8aee8e8a1e4a1d822969abee88e3a9a10b42f28 | 867 passed | Suite base; no lint adicional de main |
| Motor evaluación | a647263bcde2be074479321928b0cd74fc1c0252 | 880 passed | Ruff check/format y mypy: PASS |
| AEOS LIVE + corrección PRODUCT-002 | base 0cc8598 + diff de dos archivos del PR | 941 passed, 12 skipped | Ruff check/format, mypy (230 archivos) y git diff --check: PASS |

Los 12 skips de LIVE son 11 pruebas PostgreSQL sin DSN y una importación de Playwright no instalado. Los siete skips de main requieren PostgreSQL. No se validó aislamiento real PostgreSQL en este runner. No se habilitó renderizado automático.

Corrección publicada: [PR #39](https://github.com/Franchute10/autonomous-agent-economy/pull/39), commit `9c3ba180a6fa58f9bf6db3bc27586da7b3638277`, base LIVE `0cc8598`.

## Hallazgo reproducido y corrección

Cuatro casos sintéticos de productos/servicios reproducían que una página de oferta presente en sitemap no era inspeccionada: el selector priorizaba servicios y términos del piloto de limpieza. Se ampliaron los términos de selección con productos, catálogo, tienda, ofertas, soluciones y servicios en español. Se añadieron casos de ferretería, juguetería, consultoría y HVAC; cada caso exige páginas inspeccionadas, evidencia, prompt de corrección y ausencia de supuestos de limpieza. No demuestra búsqueda de compradores ni soporte completo de todos los rubros.

Archivos: src/aeos/live/adapters/website_inspector.py y tests/unit/application/live/test_multisector_product_entry.py. La corrección conserva límites de páginas, robots, dominio y transporte.

## Prueba de acceso real

Se intentó PublicBetaService.diagnose en dos sitios públicos de consultoría y construcción: ambos devolvieron FAILED, cero páginas y cero hallazgos. La inspección de la causa devolvió dns_error en robots.txt. Es limitación de esta ejecución, no evidencia de un defecto de las páginas. Una entrada Google Business devolvió OWNER_EVIDENCE_REQUIRED sin inspección de perfil. No hubo búsqueda live de Tavily, leads verificados, pagos ni contactos.

## Ramas e integración

Al inicio: main AEOS tenía 20 commits propios y LIVE 45; main del motor tenía 1 propio y evaluación 35. git merge-tree --write-tree no encontró conflictos textuales en ninguno de los dos pares. Esto corrige la presunción de que necesariamente habría conflictos; no autoriza integrar todos los cambios sin revisión funcional. PRs de pagos AEOS #1/#2 y la pila del motor #1/#2 requieren decisión de integración explícita.

## Parche de seguimiento revisado

Las siete diferencias de aeos-003c-followup-review se reconstruyeron desde sus blobs base en carpetas descartables y se compararon con LIVE 0cc8598:

- runbook: remoto generaliza una referencia al negocio piloto.
- business_report: remoto conserva estados de búsqueda reconocidos, evidencia registral por campo y presencia digital desconocida/reportada.
- overpass: corrige referencia de documentación para comercio de suministros de techado; consulta existente sin cambio material.
- website_inspector y test_website_inspector: remoto extrae la detección de Windows para probarla en Linux. No hay mejora local que recuperar.
- test_business_url_diagnosis: remoto corrige imports/casts; conserva las regresiones.
- test_business_profile: remoto usa datos sintéticos y estados explícitos; la copia antigua contiene identificadores reales y no debe reintroducirse.

Decisión: conservar remoto para las siete diferencias. Algunos otros fixtures remotos todavía nombran empresas piloto públicas; no confundir ese hecho con anonimización completa y revisar antes de promover el paquete.

## Inventario completo de los siete parches adjuntos

Ver PATCH_INVENTORY.json para ruta, blob de origen/destino y comparación. Cifras contra LIVE 0cc8598:

| Parche | Iguales | Diferentes | Disposición |
|---|---:|---:|---|
| 003c-followup-review | 16 | 7 | Diferencias revisadas; conservar remoto |
| 003c-followup | 12 | 7 | Copia anterior solapada; conservar para trazabilidad |
| 003c-local | 12 | 8 | Regresiones ya documentadas; no aplicar |
| followup-review-fixes | 3 | 1 | Correcciones mayormente representadas; prueba evolucionó |
| followup-test-status-fix | 0 | 1 | Archivo mal formado y corrección superada; no aplicar |
| main-source-tests | 16 | 34 | Comparación semántica completada el 2026-11-21; conservar LIVE; no reaplicar |
| main-vs-003c-core | 2 | 1 | Blob 2555b33 de real_lead_pilot.py recuperado y comparado; conservar LIVE |

No hubo rutas ausentes en LIVE entre los resultados de estos parches. Igualdad de blobs prueba igualdad de contenido; diferencia no prueba trabajo nuevo. Las 34 diferencias del parche main se reconstruyeron y revisaron semánticamente el 2026-11-21; no se reaplican las versiones antiguas. No se publican datos de negocio de los parches. La reconciliación restante se sigue por separado en AEOS #4.


## Actualización de continuidad — 2026-11-21

- Revisión de 34 diferencias completada; conservar LIVE. El archivo restante de main-vs-003c-core se recuperó y comparó; conservar LIVE. No reaplicar parches antiguos.
- Cuatro casos sintéticos pasaron mediante un harness Python directo y git diff --check. No fue una nueva corrida de pytest.
- La validación reportada en PR #39 fue 941 passed / 12 skipped sobre su base más el cambio. No atribuir esta cifra a una nueva ejecución ni a CI sin revisar los logs correspondientes.
- El intento real posterior falló por DNS antes de recuperar contenido. No demuestra calidad del sitio, disponibilidad de leads ni validación comercial.
- Esta actualización Astra es revisión y planificación; no vuelve a ejecutar suites ni implementa las tareas de Luna.
- Siguiente acción: [LUNA-001](LUNA_EXECUTION_PLAN.md), diagnóstico real. La evaluación de utilidad y fuentes se mantiene separada en LUNA-002.
