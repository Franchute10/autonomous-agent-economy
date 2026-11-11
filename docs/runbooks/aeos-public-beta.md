# AEOS Public Beta v1

La beta permite que una persona abra un enlace público, pegue una URL y reciba
un informe breve en español o inglés. El flujo reutiliza
`classify_business_url`, `WebsiteInspector` y
`build_business_url_diagnosis_report`; no altera el parser ni guarda informes.

## Qué revisa

- Sitios web HTTP(S): hasta 3 páginas, 500 KB por respuesta y 2 segundos por
  solicitud HTTP. Se revisa el HTML recibido; no se inicia sesión ni se usan
  claves de IA. Los campos cuya ausencia no pueda confirmarse quedan como
  inconclusos.
- Facebook, Instagram, LinkedIn y Google Business: no se abren ni se scrapean.
  El informe solicita una captura/exportación o acceso autorizado por el método
  oficial. Nunca pide contraseñas.
- Hasta 3 hallazgos confirmados con fragmento de evidencia y sus URLs. Los
  prompts de corrección se incluyen solo para hallazgos confirmados.

El repositorio ya tiene los contratos de dominio `AgentDefinition` y
`AgentInvocation`, pero no contiene un adaptador/runtime de modelo ejecutable.
La beta no invoca ni simula agentes: muestra el diagnóstico determinístico
existente.

## Fix Pack de prueba

El Fix Pack v1 ofrece un archivo Markdown con una plantilla y pasos por URL
para hallazgos confirmados. Excluye verificaciones inconclusas y no aplica
cambios al sitio. El precio de prueba está fijado en **USD 5**.

La compra está desactivada por defecto. Para probar Checkout en Render, añade
en **Dashboard → aeos-public-beta → Environment**:

- `AEOS_STRIPE_SECRET_KEY`: una clave **test** de Stripe que empiece por
  `sk_test_`. El servidor rechaza claves live.
- `AEOS_PUBLIC_BASE_URL`: URL HTTPS pública de la beta, sin barra final.

No pegues claves en el repositorio, comandos compartidos ni chats. Reinicia o
despliega el servicio después de definir las variables. La interfaz solo muestra
el botón si Stripe está configurado y la revisión produjo al menos una
corrección confirmada que admite el paquete. El pago se verifica consultando
directamente la sesión de Checkout antes de generar el archivo. El archivo se
reconstruye a partir de la URL y el informe vigente; no se guarda el informe.
Los enlaces largos (más de 450 caracteres) no pueden pasar por la metadata del
Checkout en esta versión.

Mientras no haya una clave de prueba, la beta gratuita funciona igual que antes
y no muestra el botón de compra. No configures una clave `sk_live_` para esta
beta.

## Límites del servicio

- 3 revisiones por dirección cliente cada 10 minutos.
- 100 revisiones por proceso y día UTC por defecto; se puede ajustar con
  `AEOS_DAILY_DIAGNOSIS_LIMIT` (1–1000).
- 2 diagnósticos simultáneos y un máximo de 8 hilos HTTP.
- Cuerpo JSON de hasta 2 KB, hasta 5 redirecciones de mismo sitio y solo
  destinos públicos HTTP(S). Cada resolución DNS se valida y la conexión se
  fija a la IP pública comprobada; la misma regla se vuelve a aplicar a cada
  redirección.
- Contadores en memoria: se reinician si el proceso se reinicia. Para la beta
  gratuita usa una sola instancia y no agregues réplicas.

Cada solicitud HTTP tiene un máximo de 2 segundos y toda la actividad HTTP de
una revisión comparte un presupuesto de 25 segundos. La resolución DNS del
sistema ocurre fuera de ese presupuesto; las dos plazas de diagnóstico y los
ocho hilos totales mantienen acotado el trabajo aunque el resolvedor tarde.

## Levantar en local

Desde la raíz del worktree, con Python 3.12 o posterior:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
$env:HOST = "127.0.0.1"
$env:PORT = "8080"
python -m aeos.live.public_beta
```

Abre <http://127.0.0.1:8080>. En macOS/Linux, crea/activa `.venv` con los
comandos propios del shell y ejecuta los mismos dos comandos `pip` y `python`.
No hacen falta Playwright, una base de datos, un modelo remoto, claves ni una
cuenta de proveedor de IA.

Para ejecutar las pruebas del transporte y del recorrido HTTP:

```powershell
python -m pytest tests/unit/live/test_public_http.py `
  tests/integration/live/test_public_beta_web.py -q
```

## Desplegar en el plan gratuito de Render

El repositorio incluye [`render.yaml`](../../render.yaml), que define un web
service Python con `/health`, escucha en `0.0.0.0:$PORT` y no declara claves ni
servicios adicionales:

1. Conecta a Render un repositorio Git que contenga esta versión y elige **New
   → Blueprint**.
2. Selecciona la rama que contiene `render.yaml` y crea el servicio
   `aeos-public-beta` en el plan **Free**.
3. Cuando el despliegue termine, visita el dominio `onrender.com` asignado y
   comprueba que `/health` responde `{"status":"ok"}`.

Render permite desplegar web services Python sin cargo en su plan Free, pero
documenta que no se recomienda para producción; el servicio se duerme tras 15
minutos sin tráfico, su sistema de archivos es efímero y puede suspenderse al
consumir cuotas. Revisa los [límites actuales del plan gratuito de
Render](https://render.com/docs/free). El Blueprint fija Python 3.12.11 porque
Render puede cambiar su versión predeterminada; confirma las versiones
compatibles en [la guía de versión Python de Render](https://render.com/docs/python-version).

`AEOS_TRUST_PROXY_HEADERS=true` está configurado para Render. En otro host,
déjalo apagado salvo que el proceso esté detrás de un proxy de confianza que
añada la IP cliente al final de `X-Forwarded-For`. La beta usa esa última IP
para el límite por cliente. La cuota diaria y la frecuencia son por proceso y
no sustituyen una capa distribuida si se escala.
