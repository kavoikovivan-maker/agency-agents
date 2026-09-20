const state = {
  agents: [],
  projects: [],
  currentProjectId: null,
  currentTaskId: null,
  pollTimer: null,
  pendingFile: null,
  activeNav: "navHome",
};

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${response.status}`);
  }
  return response.status === 204 ? null : response.json();
}

async function loadHealth() {
  const el = $("healthStatus");
  const providerEl = $("providerStatus");
  try {
    const [health, runtime] = await Promise.all([
      api("/api/health"),
      api("/api/settings/runtime"),
    ]);
    el.textContent = health.ok ? "система доступна" : "ошибка";
    el.className = `status ${health.ok ? "ok" : "bad"}`;
    providerEl.textContent = runtime.mock_mode
      ? `MOCK · ${runtime.model}`
      : `${runtime.provider.toUpperCase()} · ${runtime.model}`;
    providerEl.className = `status ${runtime.mock_mode ? "warn" : "ok"}`;
  } catch {
    el.textContent = "недоступна";
    el.className = "status bad";
    providerEl.textContent = "модель недоступна";
    providerEl.className = "status bad";
  }
}

async function loadAgents() {
  const data = await api("/api/agents");
  state.agents = data.items;
  $("count").textContent = data.count;

  const grouped = {};
  for (const item of data.items) {
    grouped[item.division] = (grouped[item.division] || 0) + 1;
  }
  $("agents").innerHTML = Object.entries(grouped)
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([name, value]) => `<div class="agent-card"><strong>${name}</strong><span>${value}</span></div>`)
    .join("");
}

async function loadProjects() {
  state.projects = await api("/api/projects");
  renderProjectList();
  if (!state.currentProjectId && state.projects.length) {
    selectProject(state.projects[0].id);
  }
}

function renderProjectList() {
  $("projectList").innerHTML = state.projects
    .map(
      (p) => `<button class="project-item ${p.id === state.currentProjectId ? "active" : ""}" data-id="${p.id}">${escapeHtml(p.name)}</button>`
    )
    .join("") || '<div class="empty">Нет проектов</div>';

  document.querySelectorAll(".project-item").forEach((btn) => {
    btn.addEventListener("click", () => selectProject(btn.dataset.id));
  });
}

async function selectProject(projectId) {
  $("departmentSummary").textContent = "Ожидание задачи";
  $("departmentLights").innerHTML = '<span class="department-empty">Отправьте задание — здесь появится маршрут между отделами.</span>';
  state.currentProjectId = projectId;
  const project = state.projects.find((p) => p.id === projectId);
  $("projectName").textContent = project ? project.name : "Проект";
  $("projectSelectBtn").textContent = project ? "Сменить проект ›" : "Выбрать или создать проект ›";
  renderProjectList();
  closeSidebar();
  await Promise.all([loadTaskHistory(), loadFiles()]);
}

async function createProject() {
  const name = prompt("Название проекта:");
  if (!name || !name.trim()) return;
  const project = await api("/api/projects", { method: "POST", body: JSON.stringify({ name: name.trim() }) });
  state.projects.unshift(project);
  await selectProject(project.id);
}

async function loadTaskHistory() {
  if (!state.currentProjectId) return;
  const tasks = await api(`/api/tasks?project_id=${state.currentProjectId}`);
  $("taskHistory").innerHTML = tasks
    .map(
      (t) => `<button class="history-item" data-id="${t.id}">
        <span class="status-dot ${statusClass(t.status)}"></span>
        <span class="history-text">${escapeHtml(truncate(t.input_text, 60))}</span>
      </button>`
    )
    .join("") || '<div class="empty">Задач пока нет</div>';

  document.querySelectorAll(".history-item").forEach((btn) => {
    btn.addEventListener("click", () => openTask(btn.dataset.id));
  });
}

async function loadFiles() {
  if (!state.currentProjectId) return;
  const files = await api(`/api/files?project_id=${state.currentProjectId}`);
  $("filesList").innerHTML = files
    .map(
      (f) => `<div class="file-item">
        <span>${escapeHtml(f.filename)}</span>
        <span class="file-meta">${(f.size / 1024).toFixed(1)} КБ${f.extraction_error ? " · ошибка извлечения текста" : ""}</span>
      </div>`
    )
    .join("") || '<div class="empty">Файлы не загружены</div>';
}

function statusClass(status) {
  return { completed: "ok", failed: "bad", cancelled: "bad", running: "busy", queued: "busy", interrupted: "warn" }[status] || "";
}

function statusLabel(status) {
  return {
    queued: "в очереди", running: "выполняется", completed: "готово",
    failed: "ошибка", cancelled: "отменено", interrupted: "прервано (можно повторить)",
  }[status] || status;
}

async function submitTask() {
  const input = $("taskInput");
  const text = input.value.trim();
  if (!text) return;
  if (!state.currentProjectId) {
    await createProject();
    if (!state.currentProjectId) return;
  }

  const fileIds = [];
  if (state.pendingFile) {
    const artifact = await uploadFile(state.pendingFile);
    if (artifact) fileIds.push(artifact.id);
  }

  const task = await api("/api/tasks", {
    method: "POST",
    body: JSON.stringify({ project_id: state.currentProjectId, input_text: text, file_ids: fileIds }),
  });
  input.value = "";
  state.pendingFile = null;
  $("attachedFile").textContent = "";
  await loadTaskHistory();
  await openTask(task.id);
  scrollToPanel("departmentPanel");
}

async function uploadFile(file) {
  const form = new FormData();
  form.append("project_id", state.currentProjectId);
  form.append("file", file);
  const response = await fetch("/api/files", { method: "POST", body: form });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    alert(`Не удалось загрузить файл: ${body.detail || response.status}`);
    return null;
  }
  const artifact = await response.json();
  await loadFiles();
  return artifact;
}

async function openTask(taskId) {
  state.currentTaskId = taskId;
  $("taskView").hidden = false;
  closeSidebar();
  clearInterval(state.pollTimer);
  const status = await refreshTask();
  if (!["completed", "failed", "cancelled"].includes(status)) {
    state.pollTimer = setInterval(refreshTask, 1500);
  }
}

async function refreshTask() {
  if (!state.currentTaskId) return;
  let task;
  try {
    task = await api(`/api/tasks/${state.currentTaskId}`);
  } catch {
    return;
  }
  renderTask(task);
  if (["completed", "failed", "cancelled"].includes(task.status)) {
    clearInterval(state.pollTimer);
    state.pollTimer = null;
    loadTaskHistory();
  }
  return task.status;
}

const DIVISION_LABELS = {
  academic: "Исследования", design: "Дизайн", engineering: "Разработка",
  finance: "Финансы", marketing: "Маркетинг", product: "Продукт",
  research: "Аналитика", sales: "Продажи", security: "Безопасность",
  specialized: "Специалисты", "project-management": "Управление",
  support: "Поддержка",
};

function renderDepartmentLights(task) {
  const lights = $("departmentLights");
  const summary = $("departmentSummary");
  const routed = [];
  // Routing events are saved before execution; TaskRun rows appear as each stage starts.
  for (const event of task.events || []) {
    if (event.level !== "routing") continue;
    const match = /^Выбран (\S+)/.exec(event.message || "");
    if (match && !routed.includes(match[1])) routed.push(match[1]);
  }
  const runs = (task.runs || []).filter((run) => run.role === "agent");
  const byId = new Map(runs.map((run) => [run.agent_id, run]));
  const divisions = new Map();
  for (const id of routed) {
    const entry = state.agents.find((agent) => agent.id === id);
    if (entry) divisions.set(entry.division, divisions.get(entry.division) || []);
  }
  for (const run of runs) {
    if (!divisions.has(run.division)) divisions.set(run.division, []);
    divisions.get(run.division).push(run);
  }
  if (!divisions.size) {
    summary.textContent = task.status === "queued" ? "В очереди" : "Маршрут определяется";
    lights.innerHTML = '<span class="department-empty">Агенты появятся после распределения задания.</span>';
    return;
  }
  const stateFor = (items, division) => {
    if (task.status === "failed" && items.some((run) => run.status === "running")) return "bad";
    if (items.some((run) => run.status === "running")) return "busy";
    if (items.some((run) => run.status === "completed") &&
        !routed.some((id) => { const a = state.agents.find((agent) => agent.id === id);
          return a && a.division === division && !byId.has(id); })) return "ok";
    return "waiting";
  };
  const items = [...divisions.entries()].map(([division, entries]) => {
    const status = stateFor(entries, division);
    const label = DIVISION_LABELS[division] || division;
    const detail = status === "busy" ? "Работает" : status === "ok" ? "Готово" :
      status === "bad" ? "Ошибка" : "Ожидает";
    return `<div class="department-tile ${status}">
      <span class="department-led ${status}" aria-hidden="true"></span>
      <strong>${escapeHtml(label)}</strong><small>${detail}</small>
    </div>`;
  });
  lights.innerHTML = items.join("");
  summary.textContent = task.status === "completed" ? "Готово" :
    task.status === "failed" ? "Ошибка выполнения" :
    task.status === "running" ? "Отделы работают" : "Ожидает запуска";
}

function renderTask(task) {
  renderDepartmentLights(task);
  $("taskStatusDot").className = `status-dot ${statusClass(task.status)}`;
  $("taskStatusLabel").textContent = statusLabel(task.status);
  $("taskMeta").textContent = task.classification ? `Классификация: ${task.classification}` : "";

  $("retryBtn").hidden = !["failed", "cancelled", "interrupted"].includes(task.status);
  $("cancelBtn").hidden = !["queued", "running"].includes(task.status);

  const routingEvents = task.events.filter((e) => e.level === "routing");
  $("routingReasonsList").innerHTML = routingEvents.length
    ? routingEvents.map((e) => `<div class="event-row">${escapeHtml(e.message)}</div>`).join("")
    : '<div class="empty">Причины выбора появятся после маршрутизации задачи.</div>';

  const planEvents = task.events.filter((e) => e.level === "plan" || e.level === "stage");
  $("executionPlanList").innerHTML = planEvents.length
    ? planEvents.map((e) => `<div class="event-row"><span class="tag">${escapeHtml(e.level)}</span> ${escapeHtml(e.message)}</div>`).join("")
    : '<div class="empty">План появится после запуска задачи.</div>';

  const agentRuns = task.runs.filter((r) => r.role === "agent");
  $("agentsUsedCount").textContent = agentRuns.length;
  $("agentsUsedList").innerHTML = task.runs
    .map(
      (r) => `<div class="agent-run">
        <div class="agent-run-head"><strong>${escapeHtml(r.agent_id)}</strong><span class="tag">${r.role}</span><span class="status-dot ${statusClass(r.status === "completed" ? "completed" : r.status)}"></span></div>
        ${r.output_text ? `<div class="agent-run-output">${escapeHtml(truncate(r.output_text, 600))}</div>` : ""}
      </div>`
    )
    .join("");

  if (task.final_answer) {
    $("finalAnswer").hidden = false;
    $("finalAnswerText").textContent = task.final_answer;
  } else {
    $("finalAnswer").hidden = true;
  }

  $("eventLog").innerHTML = task.events
    .map((e) => `<div class="event-row"><span class="tag">${e.level}</span> ${escapeHtml(e.message)}</div>`)
    .join("");

  if (task.error_message) {
    $("eventLog").innerHTML += `<div class="event-row bad">${escapeHtml(task.error_message)}</div>`;
  }
}

async function retryTask() {
  if (!state.currentTaskId) return;
  await api(`/api/tasks/${state.currentTaskId}/retry`, { method: "POST" });
  openTask(state.currentTaskId);
}

async function cancelTask() {
  if (!state.currentTaskId) return;
  await api(`/api/tasks/${state.currentTaskId}/cancel`, { method: "POST" });
  refreshTask();
}

async function openSettings() {
  const settings = await api("/api/settings/runtime");
  $("settingsBody").innerHTML = `
    <div class="settings-row"><span>Провайдер модели</span><strong>${settings.provider}</strong></div>
    <div class="settings-row"><span>Модель</span><strong>${settings.model}</strong></div>
    <div class="settings-row"><span>Настроен реальный провайдер</span><strong>${settings.configured ? "да" : "нет (используется mock)"}</strong></div>
    <div class="settings-row"><span>Агентов в каталоге</span><strong>${settings.agent_count}</strong></div>
    <div class="settings-row"><span>Макс. агентов на задачу</span><strong>${settings.max_agents_per_task}</strong></div>
    <div class="settings-row"><span>Лимит загрузки файла</span><strong>${settings.max_upload_mb} МБ</strong></div>
  `;
  $("settingsModal").hidden = false;
}

function truncate(text, n) {
  return text.length > n ? `${text.slice(0, n)}…` : text;
}

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function activateNav(id) {
  state.activeNav = id;
  for (const btn of document.querySelectorAll(".nav-tab")) {
    btn.classList.toggle("active", btn.id === id);
  }
}

function scrollToPanel(id) {
  $(id)?.scrollIntoView({behavior: "smooth", block: "start"});
}

function openSidebar() {
  $("sidebar").classList.add("open");
  $("menuBtn").setAttribute("aria-expanded", "true");
}

function closeSidebar() {
  $("sidebar").classList.remove("open");
  $("menuBtn").setAttribute("aria-expanded", "false");
}

function openHistory() {
  activateNav("navActivity");
  openSidebar();
  $("taskHistory").scrollIntoView({block: "nearest"});
}

function openProjects() {
  activateNav("navProjects");
  openSidebar();
  $("projectList").scrollIntoView({block: "nearest"});
}

function wireEvents() {
  $("newProjectBtn").addEventListener("click", createProject);
  $("submitBtn").addEventListener("click", submitTask);
  $("retryBtn").addEventListener("click", retryTask);
  $("cancelBtn").addEventListener("click", cancelTask);
  $("settingsBtn").addEventListener("click", openSettings);
  $("closeSettings").addEventListener("click", () => ($("settingsModal").hidden = true));
  $("menuBtn").addEventListener("click", () => {
    if ($("sidebar").classList.contains("open")) closeSidebar();
    else openSidebar();
  });
  $("projectSelectBtn").addEventListener("click", openProjects);
  $("quickHistory").addEventListener("click", openHistory);
  $("quickAgents").addEventListener("click", () => { activateNav("navAgents"); scrollToPanel("agentsPanel"); });
  $("quickFiles").addEventListener("click", () => scrollToPanel("filesPanel"));
  $("quickSettings").addEventListener("click", openSettings);
  $("navHome").addEventListener("click", () => { activateNav("navHome"); closeSidebar(); scrollToPanel("composerPanel"); });
  $("navProjects").addEventListener("click", openProjects);
  $("navActivity").addEventListener("click", openHistory);
  $("navAgents").addEventListener("click", () => { activateNav("navAgents"); closeSidebar(); scrollToPanel("agentsPanel"); });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { $("settingsModal").hidden = true; closeSidebar(); }
  });
  $("settingsModal").addEventListener("click", (e) => {
    if (e.target === $("settingsModal")) $("settingsModal").hidden = true;
  });
  $("fileInput").addEventListener("change", (e) => {
    state.pendingFile = e.target.files[0] || null;
    $("attachedFile").textContent = state.pendingFile ? state.pendingFile.name : "";
  });
  $("taskInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submitTask();
  });
}

async function boot() {
  wireEvents();
  await loadHealth();
  await loadAgents();
  await loadProjects();
}

boot();
