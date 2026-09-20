const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { JSDOM } = require("jsdom");

const root = path.resolve(__dirname, "..");
const html = fs.readFileSync(path.join(root, "index.html"), "utf8")
  .replace(/<script src="\/static\/app\.js"><\/script>/, "");
const dom = new JSDOM(html, { url: "https://example.test/", runScripts: "outside-only" });
const { window } = dom;
window.HTMLElement.prototype.scrollIntoView = function () { this.dataset.scrolled = "yes"; };
window.prompt = () => "Новый тестовый проект";
window.alert = (message) => { throw new Error("Unexpected UI alert: " + message); };
const calls = [];
const agents = [
  { id: "operations-manager", name: "Operations", division: "specialized" },
  { id: "product-manager", name: "Product", division: "product" },
];
let projects = [{ id: "p1", name: "Тест" }];
const task = {
  id: "task1", status: "completed", classification: "product,specialized",
  input_text: "Тест лимонада", error_message: "", final_answer: "Готовый тестовый ответ",
  events: [
    { level: "routing", message: "Выбран operations-manager | score=12" },
    { level: "routing", message: "Выбран product-manager | score=11" },
    { level: "stage", message: "Этап завершён" },
  ],
  runs: [
    { agent_id: "operations-manager", division: "specialized", role: "agent", status: "completed", output_text: "План" },
    { agent_id: "product-manager", division: "product", role: "agent", status: "completed", output_text: "Продукт" },
    { agent_id: "critic-reviewer", division: "orchestrator", role: "critic", status: "completed", output_text: "Проверка" },
  ],
};
window.fetch = async (url, opts = {}) => {
  const method = opts.method || "GET";
  calls.push(method + " " + url);
  let data;
  if (url === "/api/health") data = { ok: true };
  else if (url === "/api/settings/runtime") data = {
    mock_mode: false, model: "openai/gpt-oss-20b", provider: "groq", configured: true,
    agent_count: 264, max_agents_per_task: 4, max_upload_mb: 20,
  };
  else if (url === "/api/agents") data = { items: agents, count: 264 };
  else if (url === "/api/projects" && method === "GET") data = projects;
  else if (url === "/api/projects" && method === "POST") {
    data = { id: "p2", name: JSON.parse(opts.body).name }; projects = [data, ...projects];
  } else if (url.startsWith("/api/tasks?")) data = [];
  else if (url.startsWith("/api/files?")) data = [];
  else if (url === "/api/tasks" && method === "POST") {
    assert.equal(JSON.parse(opts.body).input_text, "Тест лимонада");
    data = { id: "task1", status: "queued" };
  } else if (url === "/api/tasks/task1") data = task;
  else throw new Error("Unexpected endpoint: " + method + " " + url);
  return { ok: true, status: 200, json: async () => data };
};

async function waitFor(predicate, label) {
  for (let i = 0; i < 80; i++) {
    if (predicate()) return;
    await new Promise((resolve) => setTimeout(resolve, 5));
  }
  throw new Error("Timed out: " + label);
}
function click(id) { window.document.getElementById(id).click(); }
const el = (id) => window.document.getElementById(id);
(async () => {
  window.eval(fs.readFileSync(path.join(root, "app.js"), "utf8"));
  await waitFor(() => el("projectName").textContent === "Тест", "initial project");
  assert.match(el("providerStatus").textContent, /GROQ/);
  assert.equal(el("count").textContent, "264");

  click("projectSelectBtn");
  assert(el("sidebar").classList.contains("open"), "Project picker must open");
  assert(!el("sidebarBackdrop").hidden, "Backdrop must appear when drawer opens");
  click("closeSidebarBtn");
  assert(!el("sidebar").classList.contains("open"), "Visible X closes the drawer");
  assert(el("sidebarBackdrop").hidden, "Backdrop must close with drawer");
  click("navProjects");
  click("sidebarBackdrop");
  assert(!el("sidebar").classList.contains("open"), "Outside tap closes drawer");
  click("projectSelectBtn");
  assert(el("sidebar").classList.contains("open"), "Project picker must reopen");
  click("navHome");
  assert(!el("sidebar").classList.contains("open"), "Home closes sidebar");
  click("quickHistory");
  assert(el("sidebar").classList.contains("open"), "History tile opens sidebar");
  click("navAgents");
  assert(!el("sidebar").classList.contains("open"), "Agents closes sidebar");
  assert.equal(el("agentsPanel").dataset.scrolled, "yes");
  click("quickFiles");
  assert.equal(el("filesPanel").dataset.scrolled, "yes");
  click("quickSettings");
  await waitFor(() => !el("settingsModal").hidden, "open settings");
  click("closeSettings");
  assert(el("settingsModal").hidden, "close settings");
  click("navProjects");
  assert(el("sidebar").classList.contains("open"));
  click("newProjectBtn");
  await waitFor(() => el("projectName").textContent === "Новый тестовый проект", "create project");
  assert(!el("sidebar").classList.contains("open"), "Creating project closes sidebar");

  el("taskInput").value = "Тест лимонада";
  click("submitBtn");
  await waitFor(() => el("taskStatusLabel").textContent === "готово", "completed task");
  assert(!el("taskView").hidden);
  assert.equal(el("finalAnswerText").textContent, "Готовый тестовый ответ");
  const lights = el("departmentLights").querySelectorAll(".department-tile.ok");
  assert.equal(lights.length, 2, "Both task departments must show completed LEDs");
  assert(calls.some((entry) => entry === "POST /api/tasks"), "Submission must call backend");
  console.log("iPhone UI smoke PASS: project selection, history, 4 quick buttons, 4 bottom tabs, settings, task submission, status lamps and answer");
  window.close();
})().catch((error) => { console.error(error); window.close(); process.exitCode = 1; });
