const copy = {
  es: {
    beta: "Beta pública gratuita",
    eyebrow: "UNA REVISIÓN CLARA. SIN CUENTA.",
    headline: "Tu sitio web,<br><em>visto con claridad.</em>",
    lede: "Pega un enlace y recibe un informe corto basado en lo que realmente muestra el sitio: hallazgos, evidencia y qué hacer después.",
    trustEvidence: "Cada hallazgo enlaza su evidencia",
    trustNoAi: "Sin claves de IA ni cuenta",
    formTitle: "¿Qué sitio revisamos?",
    urlLabel: "URL del sitio web",
    submit: "Revisar mi sitio",
    loading: "Revisando el sitio…",
    privacyNote: "Sin inicio de sesión. No guardamos el informe.",
    socialNote: "¿Un enlace de Facebook, Instagram, LinkedIn o Google Business? No hacemos scraping. Te indicaremos cómo compartir evidencia autorizada.",
    reportEyebrow: "INFORME DE REVISIÓN",
    reportTitle: "Lo que encontramos",
    confirmedTitle: "Hallazgos confirmados",
    pendingTitle: "Aún por verificar",
    confirmedEmpty: "No se confirmaron correcciones necesarias en las comprobaciones disponibles.",
    pendingEmpty: "No hay verificaciones inconclusas.",
    footerLeft: "Una herramienta de AEOS · Beta pública gratuita",
    footerRight: "Evidencia primero. Correcciones con contexto.",
    evidenceLabel: "Evidencia observada",
    sourceLabel: "Ver página de origen",
    actionLabel: "Acción sugerida",
    promptLabel: "Prompt de corrección",
    copyPrompt: "Copiar prompt",
    copied: "Copiado",
    nextLabel: "Siguiente paso",
    accessLabel: "Se requiere evidencia o acceso autorizado",
    platform: "Plataforma",
    errors: {
      invalid_url: "Ingresa una URL HTTP o HTTPS válida. No se aceptan direcciones locales o privadas.",
      invalid_language: "Elige español o inglés y vuelve a intentar.",
      rate_limit: "Llegaste al límite temporal de revisiones desde esta conexión. Espera un poco y vuelve a intentar.",
      daily_limit: "La beta alcanzó su límite gratuito de revisiones por hoy.",
      busy: "Hay dos revisiones en curso. Inténtalo de nuevo en unos segundos.",
      diagnosis_unavailable: "No se pudo completar la revisión. Inténtalo de nuevo más tarde.",
      unknown: "Ocurrió un problema. Revisa la URL e inténtalo de nuevo."
    }
  },
  en: {
    beta: "Free public beta",
    eyebrow: "A CLEAR REVIEW. NO ACCOUNT.",
    headline: "Your website,<br><em>seen clearly.</em>",
    lede: "Paste a link for a short report grounded in what the site actually shows: findings, evidence, and a practical next step.",
    trustEvidence: "Every finding links to its evidence",
    trustNoAi: "No AI key or account required",
    formTitle: "Which site should we review?",
    urlLabel: "Website URL",
    submit: "Review my website",
    loading: "Reviewing the website…",
    privacyNote: "No sign-in. We do not save your report.",
    socialNote: "A Facebook, Instagram, LinkedIn, or Google Business link? We do not scrape these services. We’ll explain how to share authorized evidence.",
    reportEyebrow: "SITE REVIEW",
    reportTitle: "What we found",
    confirmedTitle: "Confirmed findings",
    pendingTitle: "Still to verify",
    confirmedEmpty: "No corrections were confirmed as necessary in the available checks.",
    pendingEmpty: "There are no inconclusive checks.",
    footerLeft: "An AEOS tool · Free public beta",
    footerRight: "Evidence first. Corrections with context.",
    evidenceLabel: "Observed evidence",
    sourceLabel: "Open source page",
    actionLabel: "Suggested action",
    promptLabel: "Correction prompt",
    copyPrompt: "Copy prompt",
    copied: "Copied",
    nextLabel: "Next step",
    accessLabel: "Evidence or authorized access required",
    platform: "Platform",
    errors: {
      invalid_url: "Enter a valid HTTP or HTTPS URL. Local and private network addresses are not accepted.",
      invalid_language: "Choose Spanish or English and try again.",
      rate_limit: "You’ve reached the temporary review limit from this connection. Wait a little and try again.",
      daily_limit: "The beta has reached its free daily review limit.",
      busy: "Two reviews are already in progress. Try again in a few seconds.",
      diagnosis_unavailable: "The review could not be completed. Please try again later.",
      unknown: "Something went wrong. Check the URL and try again."
    }
  }
};

let language = "es";
let latestReport = null;
const form = document.querySelector("#diagnosis-form");
const button = document.querySelector("#submit-button");
const feedback = document.querySelector("#feedback");
const reportPanel = document.querySelector("#report");

function localized(value) {
  if (value && typeof value === "object") return value[language] ?? value.es ?? "";
  return value ?? "";
}

function setLanguage(nextLanguage) {
  language = nextLanguage;
  document.documentElement.lang = language;
  document.querySelectorAll("[data-i18n]").forEach((element) => {
    const key = element.dataset.i18n;
    const translated = copy[language][key];
    if (translated) element.innerHTML = translated;
  });
  document.querySelectorAll(".language-button").forEach((element) => {
    const active = element.dataset.language === language;
    element.classList.toggle("is-active", active);
    element.setAttribute("aria-pressed", String(active));
  });
  if (latestReport) renderReport(latestReport);
}

document.querySelectorAll(".language-button").forEach((element) => {
  element.addEventListener("click", () => setLanguage(element.dataset.language));
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  feedback.hidden = true;
  reportPanel.hidden = true;
  button.disabled = true;
  button.querySelector("[data-i18n]").textContent = copy[language].loading;

  try {
    const response = await fetch("/api/diagnose", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: normalizeUrl(document.querySelector("#site-url").value),
        language
      })
    });
    const result = await response.json();
    if (!response.ok) {
      showError(result.error, response.headers.get("Retry-After"));
      return;
    }
    latestReport = result;
    renderReport(result);
    reportPanel.hidden = false;
    reportPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch {
    showError("unknown");
  } finally {
    button.disabled = false;
    button.querySelector("[data-i18n]").textContent = copy[language].submit;
  }
});

function showError(code, retryAfter) {
  const message = copy[language].errors[code] || copy[language].errors.unknown;
  feedback.textContent = message;
  if (code === "rate_limit" && retryAfter) {
    const seconds = Number(retryAfter);
    if (Number.isFinite(seconds) && seconds > 0 && seconds <= 3600) {
      feedback.textContent += ` (${seconds}s)`;
    }
  }
  feedback.classList.add("is-error");
  feedback.hidden = false;
  feedback.scrollIntoView({ behavior: "smooth", block: "center" });
}

function renderReport(data) {
  const reportCopy = copy[language];
  document.querySelector("#summary").textContent = localized(data.summary);
  const chip = document.querySelector("#platform-chip");
  chip.textContent = data.platform.replaceAll("_", " ");
  document.querySelector("#confirmed-count").textContent = data.confirmed_findings.length;
  document.querySelector("#pending-count").textContent = data.pending_verifications.length;
  fillList("confirmed-list", "confirmed-empty", data.confirmed_findings, true);
  fillList("pending-list", "pending-empty", data.pending_verifications, false);
  document.querySelector("#limits").textContent = localized(data.limits);

  const access = document.querySelector("#access-request");
  if (data.access_request) {
    access.replaceChildren();
    const title = document.createElement("strong");
    title.textContent = reportCopy.accessLabel;
    const text = document.createElement("p");
    text.textContent = localized(data.access_request);
    access.append(title, text);
    access.hidden = false;
  } else {
    access.hidden = true;
  }
}

function fillList(containerId, emptyId, entries, confirmed) {
  const container = document.getElementById(containerId);
  container.replaceChildren();
  document.getElementById(emptyId).hidden = entries.length > 0;
  for (const item of entries) container.append(createFindingCard(item, confirmed));
}

function createFindingCard(item, confirmed) {
  const card = document.createElement("article");
  card.className = "finding-card";
  const top = document.createElement("div");
  top.className = "finding-card-top";
  const number = document.createElement("span");
  number.className = "finding-number";
  number.textContent = String(item.priority).padStart(2, "0");
  const title = document.createElement("h4");
  title.textContent = localized(item.title);
  top.append(number, title);
  card.append(top);

  addLabeledText(card, copy[language].evidenceLabel, localized(item.evidence), "evidence-block");
  if (item.sources?.length) {
    const links = document.createElement("div");
    links.className = "source-links";
    for (const source of item.sources) {
      const link = document.createElement("a");
      link.textContent = copy[language].sourceLabel;
      const parsed = safeLink(source.url);
      if (parsed) {
        link.href = parsed;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
      }
      const excerpt = document.createElement("span");
      excerpt.textContent = localized(source.evidence);
      links.append(link, excerpt);
    }
    card.append(links);
  }
  if (confirmed) {
    addLabeledText(card, copy[language].actionLabel, localized(item.action), "action-block");
    addPrompt(card, localized(item.correction_prompt));
  } else {
    addLabeledText(card, copy[language].nextLabel, localized(item.next_step), "action-block");
  }
  return card;
}

function addLabeledText(parent, labelText, content, className) {
  const wrapper = document.createElement("div");
  wrapper.className = className;
  const label = document.createElement("span");
  label.className = "micro-label";
  label.textContent = labelText;
  const text = document.createElement("p");
  text.textContent = content;
  wrapper.append(label, text);
  parent.append(wrapper);
}

function addPrompt(parent, promptText) {
  if (!promptText) return;
  const wrapper = document.createElement("div");
  wrapper.className = "prompt-block";
  const head = document.createElement("div");
  head.className = "prompt-head";
  const label = document.createElement("span");
  label.className = "micro-label";
  label.textContent = copy[language].promptLabel;
  const copyButton = document.createElement("button");
  copyButton.type = "button";
  copyButton.className = "copy-button";
  copyButton.textContent = copy[language].copyPrompt;
  const prompt = document.createElement("p");
  prompt.textContent = promptText;
  copyButton.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(promptText);
      copyButton.textContent = copy[language].copied;
      window.setTimeout(() => { copyButton.textContent = copy[language].copyPrompt; }, 1400);
    } catch {
      copyButton.textContent = promptText;
    }
  });
  head.append(label, copyButton);
  wrapper.append(head, prompt);
  parent.append(wrapper);
}

function safeLink(value) {
  try {
    const url = new URL(value);
    if (url.protocol === "https:" || url.protocol === "http:") return url.href;
  } catch {
    return null;
  }
  return null;
}

function normalizeUrl(value) {
  const trimmed = value.trim();
  if (/^[a-z][a-z0-9+.-]*:/i.test(trimmed)) return trimmed;
  return `https://${trimmed}`;
}
