// Results page: chart, live assumption changes, copy summary, sharing.
(() => {
  const inp = JSON.parse(document.getElementById("inp-data").textContent);
  let est = JSON.parse(document.getElementById("est-data").textContent);
  const original = JSON.parse(JSON.stringify(inp));
  HSP.store.set("hsp_solar", inp);
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  let chart = null;

  function drawChart() {
    if (!window.Chart) return;
    const data = {
      labels: months,
      datasets: [
        { type: "bar", label: "Solar used at home", data: est.monthly_self_kwh, backgroundColor: "#f2a900", stack: "s" },
        { type: "bar", label: "Solar sent to grid", data: est.monthly_export_kwh, backgroundColor: "#f7d36b", stack: "s" },
        { type: "line", label: "Your use", data: est.monthly_use_kwh, borderColor: "#1f4e78", backgroundColor: "#1f4e78", pointRadius: 0, borderWidth: 2 },
      ],
    };
    const opts = { responsive: true, maintainAspectRatio: false, animation: false,
      plugins: { legend: { position: "bottom" }, tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${HSP.num(c.parsed.y, 0)} kWh` } } },
      scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, beginAtZero: true, title: { display: true, text: "kWh per month" } } } };
    if (chart) { chart.data = data; chart.update(); } else { chart = new Chart(document.getElementById("chart"), { data, options: opts }); }
  }

  const range = (a, b, f) => `${f(a)} – ${f(b)}`;
  function render(ex) {
    const set = (id, t) => { document.getElementById(id).textContent = t; };
    set("f-size", `${HSP.num(est.size_low_kwp)}–${HSP.num(est.size_high_kwp)} kWp`);
    set("f-size-used", HSP.num(est.size_kwp));
    set("f-sav", range(est.conservative.yearly_savings_php, est.optimistic.yearly_savings_php, HSP.php));
    set("f-cost", range(est.optimistic.cost_php, est.conservative.cost_php, HSP.php));
    set("f-pb", `${HSP.num(est.optimistic.payback_years)} – ${est.conservative.payback_years === null ? "25+" : HSP.num(est.conservative.payback_years)} years`);
    set("f-bill", `${HSP.php(est.bill_before_php)} → about ${HSP.php(est.bill_after_php)}`);
    set("f-net", range(est.conservative.net_25y_php, est.optimistic.net_25y_php, HSP.php));
    const v = document.getElementById("verdict");
    v.className = "verdict verdict-" + est.verdict;
    set("v-title", ex.title); set("v-line", ex.paragraphs[0]);
    const box = document.getElementById("explain");
    box.replaceChildren();
    ex.paragraphs.slice(1).forEach((p) => { const el = document.createElement("p"); el.textContent = p; box.appendChild(el); });
    if (ex.tips.length) {
      const ul = document.createElement("ul");
      ex.tips.forEach((t) => { const li = document.createElement("li"); li.textContent = t; ul.appendChild(li); });
      box.appendChild(ul);
    }
    drawChart();
  }

  const form = document.getElementById("assumptions");
  let timer = null;
  function overrides() {
    const o = {};
    form.querySelectorAll("input[name]").forEach((i) => {   // send only values the user changed
      const v = parseFloat(i.value);
      if (!Number.isNaN(v) && i.value !== i.defaultValue) o[i.name] = v;
    });
    return o;
  }
  async function recalc() {
    inp.overrides = overrides();
    try {
      const r = await HSP.postJSON("/api/solar/estimate", inp);
      est = r.estimate; render(r.explain);
      HSP.store.set("hsp_solar", inp);
    } catch (e) { /* keep last good result */ }
  }
  form.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(recalc, 300); });
  document.getElementById("reset").addEventListener("click", () => {
    form.querySelectorAll("input[name]").forEach((i) => { i.value = i.defaultValue; });
    recalc();
  });

  document.getElementById("copy").addEventListener("click", async () => {
    const lines = [
      "HomeSolarPH estimate (indicative only, not a quotation)",
      `Region: ${est.region_name}; use ${HSP.num(est.kwh_month, 0)} kWh a month; rate PHP ${HSP.num(est.rate_per_kwh, 2)} per kWh`,
      `Suggested size: ${HSP.num(est.size_low_kwp)}-${HSP.num(est.size_high_kwp)} kWp (figures for ${HSP.num(est.size_kwp)} kWp)`,
      `Yearly savings: ${HSP.php(est.conservative.yearly_savings_php)} - ${HSP.php(est.optimistic.yearly_savings_php)}`,
      `Installed cost: ${HSP.php(est.optimistic.cost_php)} - ${HSP.php(est.conservative.cost_php)}`,
      `Payback: ${HSP.num(est.optimistic.payback_years)} - ${est.conservative.payback_years === null ? "25+" : HSP.num(est.conservative.payback_years)} years`,
      "", "Questions for installers:",
      ...[...document.querySelectorAll(".checklist li")].map((li) => "- " + li.textContent),
    ];
    try { await navigator.clipboard.writeText(lines.join("\n")); document.getElementById("copy").textContent = "Copied"; }
    catch (_) { window.prompt("Copy this summary:", lines.join("\n")); }
  });

  HSP.setupShare(() => ({ kind: "check", solar: inp }));
  drawChart();
})();
