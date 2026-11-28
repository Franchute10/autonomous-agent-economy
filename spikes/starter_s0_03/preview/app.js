"use strict";

const API_BASE = window.AEOS_API_BASE || "https://aeos-starter-api.frank-2e.workers.dev";
const ACCESS_TOKEN_KEY = "aeos_access_token";
const statusElement = document.getElementById("status");
const workspaceStatusElement = document.getElementById("workspace-status");
const authPanel = document.getElementById("auth-panel");
const workspacePanel = document.getElementById("workspace-panel");
const loginForm = document.getElementById("login-form");
const signupForm = document.getElementById("signup-form");
const organizationForm = document.getElementById("organization-form");
const organizationList = document.getElementById("organization-list");
let authConfig = null;

function setStatus(message, kind) {
  const target = workspacePanel && !workspacePanel.hidden ? workspaceStatusElement : statusElement;
  target.textContent = message;
  target.dataset.kind = kind || "info";
}

function setBusy(form, busy) {
  for (const control of form.querySelectorAll("button,input")) {
    control.disabled = busy;
  }
}

function showAuth(message) {
  workspacePanel.hidden = true;
  authPanel.hidden = false;
  if (message) setStatus(message);
}

function showWorkspace() {
  authPanel.hidden = true;
  workspacePanel.hidden = false;
}

async function readJson(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

async function loadConfig() {
  const response = await fetch(API_BASE + "/api/v1/public-config", {
    method: "GET",
    credentials: "omit",
    cache: "no-store",
    headers: { Accept: "application/json" }
  });
  const data = await readJson(response);
  if (!response.ok || !data || !data.supabase_url || !data.supabase_publishable_key) {
    throw new Error("configuration_unavailable");
  }
  authConfig = data;
}

async function authRequest(path, payload) {
  const response = await fetch(authConfig.supabase_url + path, {
    method: "POST",
    credentials: "omit",
    cache: "no-store",
    headers: {
      apikey: authConfig.supabase_publishable_key,
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
  return { response, data: await readJson(response) };
}

function setAuthMode(mode) {
  const loginSelected = mode === "login";
  loginForm.hidden = !loginSelected;
  signupForm.hidden = loginSelected;
  for (const button of document.querySelectorAll("[data-auth-mode]")) {
    button.setAttribute("aria-pressed", String(button.dataset.authMode === mode));
  }
  setStatus("");
}

async function handleAuth(form, mode) {
  const values = new FormData(form);
  const email = String(values.get("email") || "").trim();
  const password = String(values.get("password") || "");
  if (mode === "signup" && password.length < 12) {
    setStatus("La contraseña debe tener al menos 12 caracteres.", "error");
    return;
  }
  setBusy(form, true);
  setStatus(mode === "signup" ? "Creando tu cuenta…" : "Validando tu acceso…");
  try {
    const path = mode === "signup" ? "/auth/v1/signup" : "/auth/v1/token?grant_type=password";
    const result = await authRequest(path, { email, password });
    if (!result.response.ok) {
      setStatus("No pudimos completar el acceso. Revisa los datos e inténtalo de nuevo.", "error");
      return;
    }
    const token = result.data && result.data.access_token;
    if (!token) {
      setStatus("Cuenta creada. Confirma tu correo y luego ingresa.");
      setAuthMode("login");
      return;
    }
    sessionStorage.setItem(ACCESS_TOKEN_KEY, token);
    await loadOrganizations();
  } catch {
    setStatus("El servicio de acceso no está disponible. Inténtalo de nuevo.", "error");
  } finally {
    setBusy(form, false);
  }
}

async function apiRequest(path, options) {
  const token = sessionStorage.getItem(ACCESS_TOKEN_KEY);
  const headers = Object.assign({ Accept: "application/json" }, options.headers || {});
  if (token) headers.Authorization = "Bearer " + token;
  return fetch(API_BASE + path, Object.assign({}, options, {
    credentials: "omit",
    cache: "no-store",
    headers
  }));
}

function renderOrganizations(items) {
  organizationList.replaceChildren();
  if (!items.length) {
    const empty = document.createElement("p");
    empty.className = "hint";
    empty.textContent = "Aún no tienes organizaciones. Crea una para iniciar tu espacio de trabajo.";
    organizationList.appendChild(empty);
    return;
  }
  for (const item of items) {
    const card = document.createElement("article");
    card.className = "organization-item";
    const name = document.createElement("strong");
    name.textContent = item.name;
    const role = document.createElement("p");
    role.textContent = "Rol: " + item.role;
    card.append(name, role);
    organizationList.appendChild(card);
  }
}

async function loadOrganizations() {
  const response = await apiRequest("/api/v1/organizations", { method: "GET" });
  const data = await readJson(response);
  if (response.status === 401) {
    sessionStorage.removeItem(ACCESS_TOKEN_KEY);
    showAuth("La sesión venció. Ingresa nuevamente.");
    return;
  }
  if (!response.ok || !data || !Array.isArray(data.organizations)) {
    setStatus("No se pudo cargar la lista. Vuelve a intentarlo.", "error");
    return;
  }
  showWorkspace();
  renderOrganizations(data.organizations);
  setStatus("Sesión iniciada.");
}

for (const button of document.querySelectorAll("[data-auth-mode]")) {
  button.addEventListener("click", () => setAuthMode(button.dataset.authMode));
}
loginForm.addEventListener("submit", event => {
  event.preventDefault();
  void handleAuth(loginForm, "login");
});
signupForm.addEventListener("submit", event => {
  event.preventDefault();
  void handleAuth(signupForm, "signup");
});
organizationForm.addEventListener("submit", async event => {
  event.preventDefault();
  const name = String(new FormData(organizationForm).get("name") || "").trim();
  if (name.length < 2 || name.length > 120) {
    setStatus("Escribe un nombre de 2 a 120 caracteres.", "error");
    return;
  }
  setBusy(organizationForm, true);
  setStatus("Creando la organización…");
  try {
    const response = await apiRequest("/api/v1/organizations", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": crypto.randomUUID()
      },
      body: JSON.stringify({ name })
    });
    if (response.status === 401) {
      sessionStorage.removeItem(ACCESS_TOKEN_KEY);
      showAuth("La sesión venció. Ingresa nuevamente.");
      return;
    }
    if (!response.ok) {
      setStatus("No se pudo crear la organización. Revisa el nombre e inténtalo de nuevo.", "error");
      return;
    }
    organizationForm.reset();
    await loadOrganizations();
  } catch {
    setStatus("No se pudo conectar con AEOS. Inténtalo de nuevo.", "error");
  } finally {
    setBusy(organizationForm, false);
  }
});
document.getElementById("logout-button").addEventListener("click", () => {
  sessionStorage.removeItem(ACCESS_TOKEN_KEY);
  organizationList.replaceChildren();
  showAuth("Sesión cerrada en esta pestaña.");
});

async function start() {
  try {
    await loadConfig();
    const token = sessionStorage.getItem(ACCESS_TOKEN_KEY);
    if (token) {
      await loadOrganizations();
    } else {
      showAuth("");
    }
  } catch {
    showAuth("El acceso está temporalmente fuera de servicio.");
  }
}
void start();
