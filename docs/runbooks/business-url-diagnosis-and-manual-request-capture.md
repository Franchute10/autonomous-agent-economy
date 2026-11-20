# Diagnóstico por URL y captura manual de solicitudes

Esta primera etapa tiene dos recorridos locales. Ninguno inicia Overpass ni
contacta a un autor.

## A. Diagnosticar una URL

Desde PowerShell en la raíz del worktree:

```powershell
$py = "C:\Users\frank\Documents\GitHub\autonomous-agent-economy\.venv\Scripts\python.exe"
$env:PYTHONPATH = Join-Path (Get-Location).Path "src"
& $py -m aeos.live.real_demo --diagnose-url "https://cmimbelacleaningllc.com/" `
  --profile "artifacts/live/host-validation/profiles/cmimbela.profile.json" `
  --output-dir "artifacts/live/url-diagnosis"
```

Para una validación manual en otro sector, usa un negocio formal solo después
de confirmar que su sitio web público y su perfil de Google Business
corresponden al mismo negocio. Un perfil de red social no demuestra por sí solo
que exista un sitio web ni un perfil de Google Business. Los perfiles ficticios
de limpieza y HVAC sirven para pruebas automáticas; no se presentan como
negocios reales.

Como ejemplos de URLs de sitio que ya se habían considerado para inspección
manual, se pueden usar:

```text
https://constructionnationgroup.com/
artifacts/live/host-validation/profiles/construction-nation-group.profile.json

```

La URL se clasifica por host. Los sitios web pasan al inspector HTTP, sujeto a
robots.txt y a sus límites de páginas, bytes y tiempo. Por seguridad,
Playwright no se selecciona automáticamente y la captura DOM no está habilitada
para el flujo de producto: Chromium resuelve conexiones por su cuenta y aún no
hay una barrera de red que aplique la validación de IP pública y evite DNS
rebinding. La inspección queda en `HTML_ONLY`; una ausencia en ese HTML no se
presenta como ausencia confirmada en el DOM renderizado. No instales ni actives
el navegador como solución para inspeccionar sitios hasta cerrar ese control.

El informe compara title, meta description y H1 por URL entre ambas vistas, y
marca el método usado. También informa H2 y enlaces de la vista renderizada
cuando está disponible; de lo contrario los etiqueta como HTML. Conserva
alertas de metadatos duplicados con las URLs involucradas. Produce como máximo
tres hallazgos confirmados con evidencia, fuente, acción y prompt de corrección.
Las ausencias cuyo DOM no está disponible o quedó parcial aparecen aparte como
verificaciones `INCONCLUSIVE`, con prompts de verificación y sin incluir esas
URLs en prompts de corrección. No calcula indexación, posiciones, tráfico ni
causalidad.

Google Business, Facebook, Instagram y LinkedIn quedan en
`OWNER_EVIDENCE_REQUIRED`: AEOS conserva la URL, no abre la plataforma ni hace
scraping, y solicita captura, exportación o acceso autorizado. No se solicitan
contraseñas. Los perfiles no se marcan como inexistentes por no abrirse.

Los perfiles adjuntos se separan en `REPORTED`, `OBSERVED` e `INFERRED`. Las
pruebas automáticas usan perfiles sintéticos por rubro. Un negocio real solo se
usa para una prueba manual cuando sus URLs públicas y la relación entre ellas
se hayan confirmado; no se infiere que exista un sitio o una ficha de Google
por tener un perfil social.

## B. Capturar una solicitud pública manualmente

Prepara un JSON con URL, texto visible y estado de acceso. Ciudad, servicio y
fecha original son opcionales; si se incluyen, deben aparecer en el texto o
fecha introducidos. `captured_at` puede omitirse para usar la hora actual.

```json
{
  "source_url": "https://www.facebook.com/groups/example/posts/123/",
  "access_status": "PUBLIC_POST_MANUALLY_VIEWED",
  "publication_date": "2026-11-08",
  "city": "Sarasota",
  "service_requested": "deep cleaning",
  "visible_text": "Looking for a deep cleaning service in Sarasota. Can anyone send an estimate?"
}
```

Valores admitidos para `access_status`:

- `PUBLIC_POST_MANUALLY_VIEWED`: una persona confirmó manualmente que el post público era visible.
- `USER_SUPPLIED_TEXT_LINK_NOT_VERIFIED`: el texto fue pegado, pero no se comprobó el enlace.

Ejecuta:

```powershell
& $py -m aeos.live.opportunity_inbox_pilot capture-request `
  --input "request.json" `
  --output-dir "artifacts/live/manual-request-captures"
Remove-Item Env:PYTHONPATH
```

El resultado conserva URL, hora de captura, fecha de publicación si se aportó,
acceso, ciudad/servicio copiados del texto y fragmento de evidencia. La intención
explícita se deriva de una solicitud textual concreta; aun así,
`buyer_confirmed` siempre queda en `false`. El comando no abre URLs, no automatiza
grupos y no manda mensajes.

## Validación local

Con el Python 3.12+ y pytest del entorno del proyecto:

```powershell
& $py -m pytest tests/unit/application/live/test_business_url_diagnosis.py `
  tests/unit/application/live/test_manual_request_capture.py `
  tests/unit/live/test_website_inspector.py `
  tests/unit/live/test_website_intelligence.py `
  tests/unit/live/test_real_demo_website_cli.py -q
```

Los fixtures `tests/unit/live/fixtures/opportunity_inbox/manual_request_*.json`
permiten comprobar tanto una solicitud explícita como texto que no expresa
intención de contratar.
