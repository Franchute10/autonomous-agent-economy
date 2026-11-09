# AEOS-LIVE-003B3 — Generalización y remediación de seguridad

## 1. Resultado y alcance

Trabajo realizado en `codex/aeos-live-003b-checkpoint`, con `HEAD` en
`9733f69e89aa63f5507321df4a1c4f4a60defe19`. El repositorio original no fue
modificado. No se cambió de rama, no se prepararon archivos para commit y no
se hizo commit, merge, rebase ni push. No se modificaron migraciones. Los
artefactos preexistentes de `.pytest-tmp-live003b/` se conservaron.

El checkpoint ya tenía cambios sin commit y archivos sin seguimiento de
LIVE-003B. La lista de archivos al final distingue los tocados por 003B3; los
cambios anteriores se conservaron sin limpiar ni reemplazar.

## 2. Hallazgos iniciales

- El calificador de oportunidades y el planificador de consultas heredaban
  vocabulario de limpieza y ciudades fijas. La selección de perfil no llegaba a
  todos los flujos de evaluación.
- Los reportes de mercado no separaban de forma suficiente el ajuste del
  prospecto (`BUYER_FIT`) de la intención de compra (`BUYING_INTENT`). La
  taxonomía de limpieza tampoco ofrecía categorías equivalentes para HVAC y
  construcción.
- El inspector web podía conservar parámetros de URL que transportan
  credenciales o tokens y persistir valores de URL en el informe.
- `.pytest-tmp-live003b/` ya contenía archivos locales y una base SQLite. No se
  eliminó nada; las reglas de exclusión se ampliaron para impedir que nuevos
  temporales, bases locales y reportes privados entren en un cambio futuro.
- El workflow PostgreSQL no tenía disparador para pull requests hacia `main`.
- La rama de checkpoint no contiene los tres commits históricos investigados;
  la rama `main` local sí los contiene. El análisis de privacidad encontró
  perfiles e investigación comercial identificables en ese historial local.

## 3. Correcciones

- Se amplió el registro de verticales con Cleaning Services, HVAC,
  Construction, Roofing y `OTHER`; `HOUSE_CLEANING` se conserva como alias
  legado. Los alias y las categorías de servicio se resuelven dentro de la
  vertical declarada. Se añadió `B2B2C` al modelo comercial.
- El scoring usa el perfil seleccionado para servicios, geografía, segmentos,
  modelo comercial y capacidad. Cada componente conserva las evidencias que lo
  respaldan. La falta de perfil produce `INSUFFICIENT_EVIDENCE`; una
  incompatibilidad de servicio o cobertura produce `COLD`. El ajuste comercial
  por sí solo no establece intención de compra ni produce `HOT`.
- La investigación de mercado valida la vertical seleccionada y usa servicios
  declarados por el perfil para mostrar señales públicas compatibles. Los
  tipos de competidor usan la taxonomía de su propia vertical. `BUYER_FIT`,
  `BUYING_INTENT` y señales públicas actuales permanecen separados.
- El plan de consultas del piloto de oportunidades se genera con los mercados,
  servicios y vertical del perfil. El scoring del piloto recibe el mismo
  perfil. El almacenamiento local predeterminado se separa por ID de
  organización o nombre de perfil; el CLI sigue siendo offline y no sustituye
  los servicios multi-tenant.
- Se añadió una política de URL que rechaza claves sensibles antes de HTTP,
  quita fragmentos y parámetros de seguimiento, y conserva parámetros
  funcionales no sensibles. Los informes sanitizan URL y texto incrustado; no
  se almacenan cookies ni credenciales.
- Se añadió el disparador `pull_request` hacia `main` al workflow PostgreSQL.
  Conserva permisos `contents: read`, servicio PostgreSQL desechable y roles
  separados `aeos_migrator` / `aeos_app` sin secretos de repositorio.
- `.gitignore` ahora cubre directorios temporales de pytest, SQLite, bases
  locales y reportes privados. Los archivos ya existentes no se borraron.

## 4. Arquitectura anterior y actual

| Área | Antes | Actual |
| --- | --- | --- |
| Servicios | Reglas compartidas inclinadas a limpieza | Taxonomía por vertical; las ofertas se leen del perfil de la organización |
| Mercados | Ciudades de ejemplo en el plan del piloto | Áreas de servicio confirmadas o configuradas por perfil |
| Scoring | Ajuste, intención y servicio podían mezclarse | Nueve componentes explicables con IDs de evidencia y perfil explícito |
| Vertical | Compatibilidad centrada en limpieza | Cleaning Services, HVAC, Construction, Roofing y categoría extensible |
| Investigación | Etiquetas y señales con supuesto sectorial | Registros de mercado y señales con vertical; incompatibilidades fallan cerradas |
| URLs | Parámetros de consulta podían sobrevivir al informe | Claves sensibles rechazadas antes de HTTP; tracking y fragmentos eliminados |
| Aislamiento | Pilotos locales basados en rutas seleccionadas | Los servicios multi-tenant existentes usan `TenantContext`; los CLIs siguen offline |

Los máximos de los componentes de scoring son: intención 15, geografía 15,
servicio 15, segmento 5, recencia 15, estado abierto 15, canal autorizado 10,
calidad de evidencia 5 y capacidad 5. Los límites y la vigencia aún requieren
revisión humana según el tipo de oportunidad.

## 5. Verticales

- **Cleaning Services:** residencial, rotación de alquiler vacacional,
  limpieza profunda, recurrente y comercial.
- **HVAC:** instalación y reparación de aire acondicionado, mantenimiento
  preventivo, contratos comerciales y emergencias.
- **Construction:** contratación general, remodelación, construcción
  comercial/residencial y subcontratación especializada.
- **Roofing:** instalación, reparación, reemplazo e inspección.
- **Other/custom:** clave extensible; los servicios se comparan por texto
  normalizado hasta que se configure una taxonomía específica.

Las listas son taxonomías del producto, no afirmaciones sobre ninguna empresa.
Las categorías genéricas no se convierten en servicios confirmados.

## 6. Pruebas agregadas

- `tests/unit/application/live/test_opportunity_inbox.py`: compatibilidad de
  Cleaning, HVAC y Construction; servicio y ciudad incompatibles; ajuste sin
  intención; perfil ausente; evidencia de segmento y capacidad.
- `tests/unit/live/test_market_intelligence.py`: señal pública limitada al
  servicio configurado y clasificación de competidor específica de HVAC y
  Construction, incluida una sustitución de vertical incompatible.
- `tests/unit/live/test_real_lead_pilot.py`: el plan de consultas toma los
  servicios y mercados del perfil HVAC; las pruebas existentes usan un perfil
  sintético que coincide con sus escenarios.
- `tests/unit/live/test_website_inspector.py` y
  `tests/unit/application/live/test_website_intelligence.py`: rechazo de URL
  con token antes de HTTP y ausencia de secretos en reportes.
- Se mantuvieron las pruebas de duplicados, autorización, aislamiento y
  migración. No se rebajaron expectativas para obtener el resultado positivo.

## 7. Validaciones ejecutadas

El entorno Python usado fue el del `.venv` existente, con `PYTHONPATH` apuntando
a `src/` de este worktree.

| Validación | Resultado |
| --- | --- |
| `pytest -q tests` | **832 passed, 11 skipped** (4.45 s) |
| `ruff check src tests` | **All checks passed** |
| `ruff format --check src tests` | **209 files already formatted** |
| `mypy src` | **Success**, 152 archivos de fuente |
| `alembic history` | `0002_org_business_profiles` es `head`; enlaza con `0001_initial_persistence` |
| `git diff --check` | Sin errores de whitespace; Git mostró avisos de conversión LF/CRLF para `.gitignore` y `vertical.py` |
| Aislamiento de tres tenants | Suite completa y ejecución dedicada: **1 passed** |
| Migración 0002 offline | Incluida y aprobada en la suite completa |

Las 11 pruebas omitidas corresponden a PostgreSQL. En esta sesión no estaban
configuradas `AEOS_TEST_DATABASE_URL` ni `AEOS_MIGRATION_DATABASE_URL`; no se
ejecutó PostgreSQL ni se afirma una validación RLS local para 003B3. La suite
completa sí ejercitó SQLite y aislamiento a nivel de aplicación, que no
sustituyen PostgreSQL/RLS. Se recopilaron los 11 casos del archivo de
integración. El workflow configura los dos DSN de prueba con credenciales
desechables para CI; su ejecución en GitHub queda pendiente.

## 8. Seguridad, privacidad e historial

La revisión histórica fue de solo lectura y excluyó por completo `.aeos-private/`
y `linkedin-leadgen/`. No se copiaron datos de esos commits al checkpoint.

- **`f45411f` — presente en `main` local:** se detectó un perfil de empresa no
  marcado como ficticio en
  `examples/live/business_profiles/[redacted]_cleaning.json`. Contiene
  identidad comercial, entidad legal, sitio web, servicios, áreas geográficas
  y capacidad operativa. El perfil no tenía dirección postal, código postal,
  teléfono ni correo.
- El mismo commit añade
  `examples/live/market_research/[redacted]_2026-11-07.json`: 13 organizaciones
  (5 competidores, 6 compradores potenciales y 2 socios de referencia), 9
  direcciones públicas, 13 canales de contacto y 13 referencias de sitio o
  listado. Incluye notas de buyer-fit/referencia. No contiene IDs de evidencia
  de intención de compra; esos compradores potenciales no son solicitudes
  activas. El archivo incluye referencias a empresas identificables.
- **`40e1e9d` — presente en `main` local:** no añade perfiles ni registros
  JSON de prospectos. Repite referencias empresariales en código, pruebas y
  documentación; los valores de teléfono detectados en el texto relacionado
  parecían ejemplos sintéticos.
- **`9847fce` — presente en `main` local:** tampoco añade perfiles ni campos
  estructurados de contacto o dirección. Incluye referencias empresariales en
  código, pruebas, documentación y un JSON de ejemplo.
- En los refs locales, los tres commits están contenidos por `main` y no por
  `origin/main`, cuyo puntero está en el commit base del checkpoint. No se
  consultó el servidor remoto; esta conclusión describe las referencias
  disponibles localmente.

El riesgo de integrar `main` local sin una decisión de privacidad es alto: el
historial introduce identidad, datos operativos y una muestra de investigación
comercial con direcciones, canales de contacto y posibles compradores. No se
modificaron ni reescribieron esos commits. Recomiendo mantenerlos fuera de una
integración publicable hasta que el propietario revise y apruebe una
remediación de historial separada.

## 9. Riesgos pendientes

- Ejecutar los 11 tests PostgreSQL/RLS en CI o en un entorno con los dos DSN.
- Integrar una frontera de autenticación de producción. `TenantPrincipal` no
  es una prueba de identidad y un cliente con credenciales SQL puede cambiar
  la variable que usa RLS.
- RLS cubre la tabla de perfiles empresariales, no todas las tablas
  relacionales. Los CLIs y sus reportes JSON siguen siendo herramientas
  offline sin resolución de tenant.
- El conector Overpass conserva mapeos de categorías específicos de limpieza y
  el extractor de servicios del sitio sigue orientado a limpieza. HVAC y
  Construction requieren mapeos de fuentes revisados antes de discovery en
  vivo; los flujos no inventan categorías cuando faltan.
- Revisar la retención, restauración y eliminación de reportes y artefactos
  privados antes de producción.
- Resolver el historial local identificado antes de fusionar o publicar una
  rama que lo contenga.

## 10. Lista exacta de archivos tocados por LIVE-003B3

### Modificados

- `.gitignore`
- `.github/workflows/postgresql-security.yml`
- `docs/architecture/multi-tenancy.md`
- `src/aeos/application/live/assess_business.py`
- `src/aeos/application/live/market_intelligence.py`
- `src/aeos/application/live/opportunity_inbox.py`
- `src/aeos/application/live/website_report.py`
- `src/aeos/live/adapters/website_inspector.py`
- `src/aeos/live/domain/__init__.py`
- `src/aeos/live/domain/market_intelligence.py`
- `src/aeos/live/domain/opportunity_inbox.py`
- `src/aeos/live/domain/profile.py`
- `src/aeos/live/domain/vertical.py`
- `src/aeos/live/real_demo.py`
- `src/aeos/live/real_lead_pilot.py`
- `tests/unit/application/live/test_opportunity_inbox.py`
- `tests/unit/application/live/test_website_intelligence.py`
- `tests/unit/live/test_market_intelligence.py`
- `tests/unit/live/test_real_lead_pilot.py`
- `tests/unit/live/test_website_inspector.py`

### Nuevos

- `docs/architecture/multi-vertical-intelligence.md`
- `docs/research/AEOS-LIVE-003B3.md`
- `src/aeos/live/domain/url_policy.py`

No se añadieron cambios a `migrations/versions/0001_initial_persistence.py`
ni a `migrations/versions/0002_org_business_profiles.py`.

## 11. Recomendación

**GO para cerrar la remediación de código LIVE-003B3 en este checkpoint**,
sujeto a revisión del informe y a que CI ejecute las pruebas PostgreSQL/RLS.
**NO-GO para integrar o publicar el historial de `main` local** hasta tratar
separadamente los datos comerciales identificables señalados arriba. LIVE-003C
no se inició.
