async function boot() {
  const status = document.getElementById("status");
  const count = document.getElementById("count");
  const agents = document.getElementById("agents");

  try {
    const health = await fetch("/api/health").then(r => r.json());
    status.textContent = health.ok ? "система доступна" : "ошибка";
    status.classList.add(health.ok ? "ok" : "bad");

    const data = await fetch("/api/agents").then(r => r.json());
    count.textContent = data.count;

    const grouped = {};
    for (const item of data.items) {
      grouped[item.division] ||= 0;
      grouped[item.division] += 1;
    }

    agents.innerHTML = Object.entries(grouped)
      .map(([name, value]) => `<div class="agent-card"><strong>${name}</strong><span>${value}</span></div>`)
      .join("");
  } catch (e) {
    status.textContent = "недоступна";
    status.classList.add("bad");
    agents.innerHTML = '<div class="empty">Не удалось загрузить каталог.</div>';
  }
}
boot();
