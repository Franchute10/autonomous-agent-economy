"""Small dependency-free public web entry point for the AEOS beta."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import os
from pathlib import Path
import socket
import threading
import time
from typing import cast

from aeos.application.live.business_url_diagnosis import (
    BusinessURLPlatform,
    ClassifiedBusinessURL,
    build_business_url_diagnosis_report,
    classify_business_url,
)
from aeos.application.live.inspect_business_website import inspect_business_website
from aeos.live.adapters.public_http import PublicHTTPTransport
from aeos.live.adapters.website_inspector import (
    WebsiteInspectionError,
    WebsiteInspector,
    _validate_url,
)
from aeos.live.domain.url_policy import safe_url_for_report

STATIC_DIR = Path(__file__).with_name("public_beta_static")
MAX_BODY_BYTES = 2048
MAX_PER_IP = 3
RATE_WINDOW_SECONDS = 600
DEFAULT_DAILY_LIMIT = 100
MAX_WORKER_THREADS = 8
MAX_CONCURRENT_DIAGNOSES = 2
MAX_PAGE_COUNT = 3
MAX_PAGE_BYTES = 500_000
HTTP_TIMEOUT_SECONDS = 2
HTTP_TOTAL_TIMEOUT_SECONDS = 25

_TITLE_TRANSLATIONS = {
    "Metadatos ausentes en DOM renderizado": {
        "es": "Faltan metadatos confirmados",
        "en": "Confirmed missing metadata",
    },
    "H1 ausente en DOM renderizado": {
        "es": "Falta el encabezado H1",
        "en": "Missing H1 heading",
    },
    "Posibles mejoras: títulos o meta descripciones duplicados": {
        "es": "Títulos o descripciones repetidos",
        "en": "Repeated titles or descriptions",
    },
    "Posible mejora: no se identificó schema de negocio u organización": {
        "es": "No se observó schema de negocio u organización",
        "en": "Business or organization schema not observed",
    },
    "Verificación pendiente de títulos o meta descripciones": {
        "es": "Falta verificar título o meta descripción",
        "en": "Title or meta description needs verification",
    },
    "Verificación pendiente de H1": {
        "es": "Falta verificar el encabezado H1",
        "en": "H1 heading needs verification",
    },
}


class PublicInputError(ValueError):
    """A user-input error safe to return from the public endpoint."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class PublicBetaService:
    """Join the established inspector and diagnosis report for public requests."""

    def __init__(
        self,
        inspector_factory: Callable[[], WebsiteInspector] | None = None,
    ) -> None:
        self._inspector_factory = inspector_factory or _public_inspector

    def diagnose(self, submitted_url: object, language: object = "es") -> dict[str, object]:
        if not isinstance(submitted_url, str) or len(submitted_url) > 2048:
            raise PublicInputError("invalid_url")
        if not isinstance(language, str) or language not in {"es", "en"}:
            raise PublicInputError("invalid_language")
        try:
            classified = _classify_public_url(submitted_url)
        except ValueError as error:
            raise PublicInputError("invalid_url") from error

        inspection = None
        inspection_status = "NOT_STARTED"
        failure_category: str | None = None
        failure_stage: str | None = None
        inspected_at: str | None = None
        if classified.platform is BusinessURLPlatform.WEBSITE:
            inspection_status = "SUCCEEDED"
            inspected_at = datetime.now(timezone.utc).isoformat()
            try:
                inspection = inspect_business_website(
                    self._inspector_factory(), classified.url
                )
                if inspection.details is not None:
                    inspected_at = inspection.details.inspected_at.isoformat()
            except WebsiteInspectionError as error:
                inspection_status = "FAILED"
                failure_category = error.category
                failure_stage = error.stage

        report = build_business_url_diagnosis_report(
            classified.url,
            inspection=inspection,
            inspection_status=inspection_status,
            failure_category=failure_category,
            failure_stage=failure_stage,
            inspected_at=inspected_at,
        )
        return _public_projection(report, cast(str, language))


def _public_inspector() -> WebsiteInspector:
    return WebsiteInspector(
        timeout_seconds=HTTP_TIMEOUT_SECONDS,
        max_response_bytes=MAX_PAGE_BYTES,
        max_pages=MAX_PAGE_COUNT,
        transport=PublicHTTPTransport(
            total_timeout_seconds=HTTP_TOTAL_TIMEOUT_SECONDS
        ),
    )


def _classify_public_url(value: str) -> ClassifiedBusinessURL:
    classified = classify_business_url(value)
    try:
        _validate_url(classified.url, resolve_host=False)
    except WebsiteInspectionError as error:
        raise ValueError("URL is not a permitted public HTTP(S) destination") from error
    return classified


def _public_projection(
    report: Mapping[str, object], language: str
) -> dict[str, object]:
    raw_diagnosis = report.get("url_diagnosis")
    diagnosis = raw_diagnosis if isinstance(raw_diagnosis, Mapping) else {}
    platform = str(diagnosis.get("platform", "WEBSITE"))
    status = str(diagnosis.get("inspection_status", "NOT_COMPLETED"))
    signals_value = diagnosis.get("observed_signals")
    signals = signals_value if isinstance(signals_value, Mapping) else {}
    scope_value = signals.get("inspection_scope")
    scope = scope_value if isinstance(scope_value, Mapping) else {}
    page_count = scope.get("pages_received", 0)
    page_count = page_count if isinstance(page_count, int) else 0

    message = _summary_message(platform, status, page_count)
    findings = [
        _project_item(item, confirmed=True)
        for item in _as_list(diagnosis.get("findings"))
        if isinstance(item, Mapping) and item.get("observation_status") == "OBSERVED"
    ][:3]
    pending = [
        _project_item(item, confirmed=False)
        for item in _as_list(diagnosis.get("pending_verifications"))
        if isinstance(item, Mapping)
    ][:3]
    result: dict[str, object] = {
        "language": language,
        "submitted_url": diagnosis.get("submitted_url"),
        "platform": platform,
        "inspection_status": status,
        "pages_received": page_count,
        "summary": message,
        "confirmed_findings": findings,
        "pending_verifications": pending,
        "limits": {
            "es": "Revisión pública y limitada: hasta 3 páginas, 500 KB por respuesta, 2 segundos por solicitud y 25 segundos de red HTTP en total (DNS del sistema aparte). El HTML se revisa sin iniciar sesión; no se analizan posiciones ni tráfico.",
            "en": "A limited public review: up to 3 pages, 500 KB per response, 2 seconds per request, and 25 seconds of total HTTP time (system DNS excluded). HTML is reviewed without signing in; rankings and traffic are not measured.",
        },
    }
    if platform != BusinessURLPlatform.WEBSITE.value:
        result["access_request"] = {
            "es": "Para revisar Facebook, Instagram, LinkedIn o Google Business, comparte una captura o exportación de los campos pertinentes, o proporciona acceso autorizado mediante el mecanismo oficial. No envíes contraseñas.",
            "en": "To review Facebook, Instagram, LinkedIn, or Google Business, share a screenshot or export of the relevant fields, or provide authorized access through the official method. Do not send passwords.",
        }
    if status == "FAILED":
        failure_value = diagnosis.get("failure")
        failure = failure_value if isinstance(failure_value, Mapping) else {}
        result["failure_code"] = failure.get("category", "inspection_failed")
    return result


def _summary_message(platform: str, status: str, page_count: int) -> dict[str, str]:
    if platform != BusinessURLPlatform.WEBSITE.value:
        return {
            "es": "No se abrió el perfil ni se hizo scraping. Se necesita evidencia o acceso autorizado.",
            "en": "The profile was not opened or scraped. Evidence or authorized access is required.",
        }
    if status == "FAILED":
        return {
            "es": "No se pudo completar la inspección. No se confirmó ningún hallazgo.",
            "en": "The inspection could not be completed. No findings were confirmed.",
        }
    return {
        "es": f"Se revisó el HTML de {page_count} página(s). Cada hallazgo confirmado incluye evidencia y su URL de origen.",
        "en": f"Reviewed the HTML of {page_count} page(s). Each confirmed finding includes evidence and its source URL.",
    }


def _project_item(item: Mapping[str, object], *, confirmed: bool) -> dict[str, object]:
    raw_title = str(item.get("title", "Hallazgo"))
    titles = _TITLE_TRANSLATIONS.get(
        raw_title, {"es": raw_title, "en": raw_title}
    )
    evidence_value = item.get("evidence")
    evidence = evidence_value if isinstance(evidence_value, Mapping) else {}
    source_values = _as_list(evidence.get("sources"))
    sources: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for raw_source in source_values:
        if not isinstance(raw_source, Mapping):
            continue
        source_url = _public_url(raw_source.get("source_url"))
        if source_url is None or source_url in seen_urls:
            continue
        seen_urls.add(source_url)
        excerpt = raw_source.get("excerpt")
        sources.append(
            {
                "url": source_url,
                "evidence": _localize_source_excerpt(
                    raw_title, str(excerpt or "")[:500], confirmed=confirmed
                ),
            }
        )
    main_url = _public_url(evidence.get("source_url"))
    if main_url and main_url not in seen_urls:
        sources.insert(
            0,
            {
                "url": main_url,
                "evidence": _localize_source_excerpt(
                    raw_title,
                    str(evidence.get("excerpt") or "")[:500],
                    confirmed=confirmed,
                ),
            },
        )
    if not sources and main_url:
        sources.append(
            {
                "url": main_url,
                "evidence": _localize_source_excerpt(
                    raw_title,
                    str(evidence.get("excerpt") or "")[:500],
                    confirmed=confirmed,
                ),
            }
        )

    output: dict[str, object] = {
        "priority": item.get("priority"),
        "status": "OBSERVED" if confirmed else "INCONCLUSIVE",
        "title": titles,
        "evidence": _evidence_summary(raw_title, confirmed),
        "sources": sources[:5],
    }
    if confirmed:
        output.update(_confirmed_copy(raw_title, sources))
    else:
        output["observation"] = {
            "es": "El dato no se pudo confirmar con la inspección disponible.",
            "en": "This could not be confirmed with the available inspection.",
        }
        output["next_step"] = {
            "es": "Verifica este campo en una captura completa de la página antes de cambiarlo.",
            "en": "Check this field in a complete page view before changing it.",
        }
    return output


def _evidence_summary(title: str, confirmed: bool) -> dict[str, str]:
    if not confirmed:
        return {
            "es": "La observación de HTML no confirma por sí sola que el campo falte en la página renderizada.",
            "en": "The HTML observation alone does not confirm that the field is missing from the rendered page.",
        }
    if title == "Metadatos ausentes en DOM renderizado":
        return {
            "es": "El DOM renderizado no contiene los metadatos indicados en las URLs enlazadas.",
            "en": "The rendered DOM has no text for the metadata fields on the linked pages.",
        }
    if title == "H1 ausente en DOM renderizado":
        return {
            "es": "No se observó un encabezado H1 con texto en las URLs enlazadas.",
            "en": "No text H1 heading was observed on the linked pages.",
        }
    if title == "Posibles mejoras: títulos o meta descripciones duplicados":
        return {
            "es": "Se observó el mismo texto de título o meta descripción en varias páginas.",
            "en": "The same title or meta description text was observed on multiple pages.",
        }
    if title == "Posible mejora: no se identificó schema de negocio u organización":
        return {
            "es": "No se observó un tipo de schema de negocio u organización en las páginas revisadas.",
            "en": "No business or organization schema type was observed on the reviewed pages.",
        }
    return {
        "es": "La condición indicada se observó en las páginas enlazadas.",
        "en": "The stated condition was observed on the linked pages.",
    }


def _localize_source_excerpt(
    title: str, excerpt: str, *, confirmed: bool
) -> dict[str, str]:
    if confirmed and title == "Posibles mejoras: títulos o meta descripciones duplicados":
        translated = excerpt.replace("Metadato duplicado:", "Repeated metadata:", 1)
    else:
        translated = _evidence_summary(title, confirmed=confirmed)["en"]
    return {"es": excerpt, "en": translated}


def _confirmed_copy(
    title: str, sources: list[dict[str, str]]
) -> dict[str, object]:
    urls = [source["url"] for source in sources]
    url_list = ", ".join(urls[:3]) or "la página indicada"
    if title == "Metadatos ausentes en DOM renderizado":
        action = {
            "es": "Revisa esas páginas y añade solo los títulos o descripciones confirmados como ausentes, según su contenido real.",
            "en": "Review these pages and add only the confirmed missing titles or descriptions, based on their actual content.",
        }
        prompt = {
            "es": f"Corrige solo los títulos o meta descripciones confirmados como ausentes en: {url_list}. Usa el contenido real; no inventes datos.",
            "en": f"Fix only the confirmed missing titles or meta descriptions on: {url_list}. Use the actual page content; do not invent claims.",
        }
        why = {
            "es": "Un título o descripción claro ayuda a identificar el contenido de la página; la ausencia observada no demuestra una pérdida de posiciones.",
            "en": "A clear title or description helps identify a page's content; the observed absence does not prove a ranking loss.",
        }
    elif title == "H1 ausente en DOM renderizado":
        action = {
            "es": "Añade un encabezado principal claro que describa el contenido real de cada página indicada.",
            "en": "Add a clear main heading that describes the actual content of each listed page.",
        }
        prompt = {
            "es": f"Añade un H1 claro solo a estas páginas confirmadas: {url_list}. Describe su contenido real; no inventes datos.",
            "en": f"Add a clear H1 only to these confirmed pages: {url_list}. Describe their actual content; do not invent claims.",
        }
        why = {
            "es": "Un encabezado principal ayuda a las personas a entender cada página; su ausencia no demuestra una causa de posicionamiento.",
            "en": "A main heading helps people understand each page; its absence does not prove a ranking cause.",
        }
    elif title == "Posibles mejoras: títulos o meta descripciones duplicados":
        action = {
            "es": "Compara las páginas enlazadas y redacta metadatos distintos solo cuando su contenido lo justifique.",
            "en": "Compare the linked pages and write distinct metadata only when their content supports it.",
        }
        prompt = {
            "es": f"Haz únicos los títulos o descripciones repetidos de estas páginas: {url_list}. Ajusta cada uno al contenido real; no inventes datos.",
            "en": f"Make the repeated titles or descriptions unique on these pages: {url_list}. Match each to its actual content; do not invent claims.",
        }
        why = {
            "es": "Los metadatos únicos pueden distinguir páginas diferentes; la repetición no demuestra pérdida de posiciones.",
            "en": "Unique metadata can distinguish different pages; repetition does not prove a ranking loss.",
        }
    elif title == "Posible mejora: no se identificó schema de negocio u organización":
        action = {
            "es": "Evalúa si conviene añadir JSON-LD con datos empresariales confirmados.",
            "en": "Consider adding JSON-LD using confirmed business details.",
        }
        prompt = {
            "es": f"Evalúa JSON-LD para {url_list}. Usa solo datos confirmados; no inventes dirección, servicios, teléfono ni horarios.",
            "en": f"Review JSON-LD for {url_list}. Use confirmed details only; do not invent an address, services, phone, or hours.",
        }
        why = {
            "es": "El marcado estructurado puede describir el negocio a sistemas compatibles; no garantiza resultados ni posiciones.",
            "en": "Structured data can describe a business to compatible systems; it does not guarantee results or rankings.",
        }
    else:
        action = {
            "es": "Revisa el hallazgo confirmado en las páginas enlazadas y corrige solo lo que indique la evidencia.",
            "en": "Review the confirmed finding on the linked pages and address only what the evidence shows.",
        }
        prompt = {
            "es": f"Revisa el hallazgo confirmado en: {url_list}. Corrige solo la condición descrita por la evidencia; no inventes datos.",
            "en": f"Review the confirmed finding at: {url_list}. Address only the condition shown by the evidence; do not invent claims.",
        }
        why = {
            "es": "La acción está limitada al estado observado; no demuestra efectos en posiciones o resultados.",
            "en": "The action is limited to the observed state; it does not prove effects on rankings or outcomes.",
        }
    return {"action": action, "why_it_may_matter": why, "correction_prompt": prompt}


def _public_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    safe = safe_url_for_report(value)
    if not safe or safe == "[URL omitted]":
        return None
    return safe


def _as_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


class RequestGate:
    """Process-local sliding rate limit and UTC-day diagnosis budget."""

    def __init__(
        self,
        *,
        per_ip_limit: int = MAX_PER_IP,
        window_seconds: int = RATE_WINDOW_SECONDS,
        daily_limit: int = DEFAULT_DAILY_LIMIT,
    ) -> None:
        self.per_ip_limit = per_ip_limit
        self.window_seconds = window_seconds
        self.daily_limit = daily_limit
        self._lock = threading.Lock()
        self._by_ip: dict[str, deque[float]] = {}
        self._day = datetime.now(timezone.utc).date()
        self._daily_count = 0

    def consume(self, client_ip: str) -> tuple[bool, str, int]:
        now = time.monotonic()
        current_day = datetime.now(timezone.utc).date()
        with self._lock:
            if current_day != self._day:
                self._day = current_day
                self._daily_count = 0
                self._by_ip.clear()
            if self._daily_count >= self.daily_limit:
                tomorrow = datetime.combine(
                    current_day + timedelta(days=1), datetime.min.time(), timezone.utc
                )
                retry_after = max(
                    1, int((tomorrow - datetime.now(timezone.utc)).total_seconds())
                )
                return False, "daily_limit", retry_after
            hits = self._by_ip.setdefault(client_ip, deque())
            while hits and hits[0] <= now - self.window_seconds:
                hits.popleft()
            if len(hits) >= self.per_ip_limit:
                retry = max(1, int(self.window_seconds - (now - hits[0])))
                return False, "rate_limit", retry
            if len(self._by_ip) > 10_000:
                self._by_ip = {
                    key: value
                    for key, value in self._by_ip.items()
                    if value and value[-1] > now - self.window_seconds
                }
            hits.append(now)
            self._daily_count += 1
            return True, "", 0


class PublicBetaHTTPServer(ThreadingHTTPServer):
    """Bound the number of handler threads even during connection floods."""

    daemon_threads = True
    request_queue_size = 16

    def __init__(
        self,
        address: tuple[str, int],
        handler: type[BaseHTTPRequestHandler],
        *,
        max_threads: int = MAX_WORKER_THREADS,
        service: PublicBetaService | None = None,
        gate: RequestGate | None = None,
        max_concurrent_diagnoses: int = MAX_CONCURRENT_DIAGNOSES,
        trust_proxy_headers: bool = False,
    ) -> None:
        self.request_slots = threading.BoundedSemaphore(max_threads)
        self.diagnosis_slots = threading.BoundedSemaphore(max_concurrent_diagnoses)
        self.service = service or PublicBetaService()
        self.gate = gate or RequestGate()
        self.trust_proxy_headers = trust_proxy_headers
        super().__init__(address, handler)

    def process_request(
        self, request: socket.socket, client_address: tuple[str, int]
    ) -> None:
        if not self.request_slots.acquire(blocking=False):
            try:
                request.sendall(
                    b"HTTP/1.1 503 Service Unavailable\r\n"
                    b"Connection: close\r\nContent-Length: 0\r\n\r\n"
                )
            except OSError:
                pass
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.request_slots.release()
            raise

    def process_request_thread(
        self, request: socket.socket, client_address: tuple[str, int]
    ) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.request_slots.release()


class PublicBetaHandler(BaseHTTPRequestHandler):
    server_version = "AEOSPublicBeta"
    protocol_version = "HTTP/1.1"

    @property
    def beta_server(self) -> PublicBetaHTTPServer:
        return cast(PublicBetaHTTPServer, self.server)

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(10)

    def do_GET(self) -> None:
        resources = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/app.js": ("app.js", "text/javascript; charset=utf-8"),
            "/styles.css": ("styles.css", "text/css; charset=utf-8"),
        }
        if self.path == "/health":
            self._send_json(200, {"status": "ok"})
            return
        resource = resources.get(self.path)
        if resource is None:
            self._send_json(404, {"error": "not_found"})
            return
        filename, content_type = resource
        try:
            body = (STATIC_DIR / filename).read_bytes()
        except OSError:
            self._send_json(503, {"error": "static_asset_unavailable"})
            return
        self._send(200, content_type, body)

    def do_POST(self) -> None:
        if self.path != "/api/diagnose":
            self._send_json(404, {"error": "not_found"})
            return
        if self.headers.get_content_type() != "application/json":
            self._send_json(415, {"error": "content_type_required"})
            return
        try:
            content_length = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            content_length = -1
        if content_length < 0 or content_length > MAX_BODY_BYTES:
            self._send_json(413 if content_length > MAX_BODY_BYTES else 400, {"error": "invalid_body_size"})
            return

        if not self.beta_server.diagnosis_slots.acquire(blocking=False):
            self._send_json(503, {"error": "busy"}, retry_after=5)
            return
        try:
            client_ip = self._client_ip()
            allowed, reason, retry_after = self.beta_server.gate.consume(client_ip)
            if not allowed:
                self._send_json(
                    429,
                    {"error": reason},
                    retry_after=retry_after,
                )
                return
            raw_body = self.rfile.read(content_length)
            if len(raw_body) != content_length:
                self._send_json(400, {"error": "invalid_body_size"})
                return
            try:
                payload = json.loads(raw_body)
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._send_json(400, {"error": "invalid_json"})
                return
            if not isinstance(payload, dict):
                self._send_json(400, {"error": "invalid_payload"})
                return
            try:
                response = self.beta_server.service.diagnose(
                    payload.get("url"), payload.get("language", "es")
                )
            except PublicInputError as error:
                self._send_json(400, {"error": error.code})
                return
            except Exception:
                self._send_json(500, {"error": "diagnosis_unavailable"})
                return
            self._send_json(200, response)
        finally:
            self.beta_server.diagnosis_slots.release()

    def _client_ip(self) -> str:
        peer = self.client_address[0] if self.client_address else "unknown"
        if self.beta_server.trust_proxy_headers:
            forwarded = self.headers.get("X-Forwarded-For", "")
            if len(forwarded) <= 256 and forwarded.strip():
                candidate = forwarded.rsplit(",", 1)[-1].strip()
                try:
                    return str(ipaddress.ip_address(candidate))
                except ValueError:
                    pass
        return str(peer)

    def _send_json(
        self, status: int, payload: Mapping[str, object], *, retry_after: int | None = None
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
        self._send(status, "application/json; charset=utf-8", body, retry_after=retry_after)

    def _send(
        self,
        status: int,
        content_type: str,
        body: bytes,
        *,
        retry_after: int | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; img-src 'self' data:; base-uri 'none'; "
            "form-action 'self'; frame-ancestors 'none'",
        )
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if retry_after is not None:
            self.send_header("Retry-After", str(retry_after))
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def log_message(self, format: str, *args: object) -> None:
        return


def create_server(
    host: str = "127.0.0.1",
    port: int = 8080,
    *,
    service: PublicBetaService | None = None,
    gate: RequestGate | None = None,
    trust_proxy_headers: bool | None = None,
) -> PublicBetaHTTPServer:
    trusted_proxy = (
        _env_bool("AEOS_TRUST_PROXY_HEADERS", False)
        if trust_proxy_headers is None
        else trust_proxy_headers
    )
    return PublicBetaHTTPServer(
        (host, port),
        PublicBetaHandler,
        service=service,
        gate=gate,
        trust_proxy_headers=trusted_proxy,
    )


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


def main() -> int:
    try:
        port = int(os.environ.get("PORT", "8080"))
    except ValueError:
        port = 8080
    try:
        daily_limit = int(os.environ.get("AEOS_DAILY_DIAGNOSIS_LIMIT", "100"))
    except ValueError:
        daily_limit = DEFAULT_DAILY_LIMIT
    daily_limit = min(1000, max(1, daily_limit))
    server = PublicBetaHTTPServer(
        (os.environ.get("HOST", "0.0.0.0"), port),
        PublicBetaHandler,
        gate=RequestGate(daily_limit=daily_limit),
        trust_proxy_headers=_env_bool("AEOS_TRUST_PROXY_HEADERS", False),
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
