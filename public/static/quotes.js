// Quote comparison: upload or type quotes, confirm fields, compare.
(() => {
  const MAX = 4;
  const cards = document.getElementById("quote-cards");
  const tpl = document.getElementById("quote-tpl");
  const status = document.getElementById("upload-status");
  const solar = HSP.store.get("hsp_solar");
  const quotes = [];   // {el, source, original}
  let lastCompared = null;

  if (solar) {
    document.getElementById("ctx-has").hidden = false;
    document.getElementById("ctx-none").hidden = true;
    document.getElementById("ctx-text").textContent = `bill PHP ${Math.round(solar.bill_php).toLocaleString("en-PH")}, region ${solar.region}`;
  }

  const get = (obj, path) => path.split(".").reduce((o, k) => (o ? o[k] : undefined), obj);
  function readFields(el) {
    const f = { inclusions: {}, warranty_years: {} };
    el.querySelectorAll("[data-f]").forEach((i) => {
      const path = i.dataset.f.split(".");
      let v = i.value.trim();
      if (i.hasAttribute("data-bool")) v = v === "" ? null : v === "true";
      else if (i.type === "number") v = v === "" ? null : Number(v);
      else v = v === "" ? null : v;
      if (path.length === 2) f[path[0]][path[1]] = v; else f[path[0]] = v;
    });
    if (!f.label) f.label = "Quote";
    if (!f.system_type) f.system_type = "unknown";
    return f;
  }
  function fillFields(el, fields) {
    el.querySelectorAll("[data-f]").forEach((i) => {
      const v = get(fields, i.dataset.f);
      i.value = v === null || v === undefined ? "" : String(v);
    });
  }
  function countChanges(a, b) {
    let n = 0;
    const walk = (x, y) => Object.keys(x).forEach((k) => {
      if (k === "label") return;
      if (x[k] && typeof x[k] === "object") walk(x[k], y[k] || {});
      else if ((x[k] ?? null) !== (y[k] ?? null)) n++;
    });
    walk(a, b);
    return n;
  }

  function addCard(fields, source, message, text) {
    if (quotes.length >= MAX) { status.textContent = "You can compare up to 4 quotes."; return; }
    const el = tpl.content.firstElementChild.cloneNode(true);
    const letter = "ABCD"[quotes.length];
    fields.label = fields.label && fields.label !== "Quote" ? fields.label : `Quote ${letter}`;
    fillFields(el, fields);
    el.querySelector(".src").textContent = source.startsWith("ai") ? "Read automatically: please check" : "Typed in";
    el.querySelector(".qmsg").textContent = message || "";
    if (text) { const d = el.querySelector(".qtext"); d.hidden = false; d.querySelector("pre").textContent = text; }
    const q = { el, source, original: readFields(el) };
    el.querySelector(".remove").addEventListener("click", () => {
      quotes.splice(quotes.indexOf(q), 1); el.remove(); update();
    });
    quotes.push(q); cards.appendChild(el); update();
    el.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  function update() { document.getElementById("compare").disabled = quotes.length === 0; }

  async function shrinkImage(file) {
    if (!file.type.startsWith("image/")) return file;
    const img = await createImageBitmap(file).catch(() => null);
    if (!img) return file;
    const scale = Math.min(1, 1600 / Math.max(img.width, img.height));
    const c = document.createElement("canvas");
    c.width = Math.round(img.width * scale); c.height = Math.round(img.height * scale);
    c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
    return new Promise((res) => c.toBlob((b) => res(new File([b], "quote.jpg", { type: "image/jpeg" })), "image/jpeg", 0.8));
  }

  document.getElementById("file").addEventListener("change", async (ev) => {
    const file = ev.target.files[0];
    ev.target.value = "";
    if (!file) return;
    if (quotes.length >= MAX) { status.textContent = "You can compare up to 4 quotes."; return; }
    status.textContent = "Reading your quote... this can take up to a minute.";
    try {
      const small = await shrinkImage(file);
      if (small.size > 4 * 1024 * 1024) throw new Error("The file is larger than 4 MB. Try a smaller photo or a PDF.");
      const fd = new FormData();
      fd.append("file", small); fd.append("label", `Quote ${"ABCD"[quotes.length]}`);
      const r = await fetch("/api/quotes/extract", { method: "POST", body: fd });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || "Could not read the file.");
      addCard(data.fields, data.source, data.message, data.text);
      status.textContent = "";
    } catch (e) { status.textContent = e.message; }
  });
  document.getElementById("add-manual").addEventListener("click", () => addCard({}, "manual", "Type the key figures from your quote. Leave blank anything it doesn't state."));

  function td(text, cls) { const c = document.createElement("td"); c.textContent = text; if (cls) c.className = cls; return c; }
  function renderResult(res) {
    const t = document.getElementById("cmp-table");
    t.replaceChildren();
    const head = document.createElement("tr");
    head.appendChild(document.createElement("th"));
    res.quotes.forEach((q) => { const th = document.createElement("th"); th.textContent = q.label + (q.installer_name ? ` (${q.installer_name})` : ""); head.appendChild(th); });
    t.appendChild(head);
    const rows = [
      ["System size (kWp)", (q) => HSP.num(q.kwp, 2)],
      ["Size from panels listed (kWp)", (q) => HSP.num(q.kwp_from_panels, 2)],
      ["Price incl. VAT", (q) => HSP.php(q.price_incl_vat_php)],
      ["Price per watt", (q) => q.price_per_wp === null ? "-" : "PHP " + HSP.num(q.price_per_wp, 1)],
      ["Expected output per year (kWh)", (q) => HSP.num(q.yearly_gen_kwh, 0)],
      ["Price per yearly kWh", (q) => q.price_per_yearly_kwh === null ? "-" : "PHP " + HSP.num(q.price_per_yearly_kwh, 1)],
      ["Yearly savings", (q) => q.yearly_savings_low === null ? "Run the solar check" : `${HSP.php(q.yearly_savings_low)} – ${HSP.php(q.yearly_savings_high)}`],
      ["Payback (years)", (q) => q.payback_low === null ? "-" : `${HSP.num(q.payback_low)} – ${q.payback_high === null ? "25+" : HSP.num(q.payback_high)}`],
      ["Panel + inverter + workmanship warranty (years)", (q) => q.warranty_total_years ?? "-"],
      ["Points to check", (q) => String(q.flags.filter((f) => f.level === "check").length)],
    ];
    rows.forEach(([label, fn]) => {
      const tr = document.createElement("tr");
      const th = document.createElement("th"); th.textContent = label; tr.appendChild(th);
      res.quotes.forEach((q) => tr.appendChild(td(fn(q))));
      t.appendChild(tr);
    });
    const fl = document.getElementById("cmp-flags");
    fl.replaceChildren();
    res.quotes.forEach((q) => {
      const h = document.createElement("h3"); h.textContent = `${q.label}: what to check and ask`; fl.appendChild(h);
      if (!q.flags.length) { const p = document.createElement("p"); p.textContent = "Nothing flagged from the figures entered."; fl.appendChild(p); return; }
      const ul = document.createElement("ul"); ul.className = "flags";
      q.flags.forEach((f) => {
        const li = document.createElement("li"); li.className = "flag-" + f.level;
        const s = document.createElement("span"); s.textContent = f.text;
        const a = document.createElement("em"); a.textContent = " Ask: " + f.question;
        li.append(s, a); ul.appendChild(li);
      });
      fl.appendChild(ul);
    });
    const notes = document.getElementById("cmp-notes");
    notes.replaceChildren(...res.notes.map((n) => { const li = document.createElement("li"); li.textContent = n; return li; }));
    document.getElementById("result").hidden = false;
    document.getElementById("result").scrollIntoView({ behavior: "smooth" });
  }

  document.getElementById("compare").addEventListener("click", async () => {
    const qs = quotes.map((q) => readFields(q.el));
    const body = { quotes: qs };
    if (solar) body.solar = solar; else body.region = document.getElementById("region").value;
    try {
      renderResult(await HSP.postJSON("/api/quotes/compare", body));
      lastCompared = qs;
    } catch (e) { status.textContent = e.message; }
  });

  HSP.setupShare(() => lastCompared && ({
    kind: "quotes", solar: solar || null, quotes: lastCompared,
    region: solar ? null : document.getElementById("region").value,
    fields_corrected: quotes.map((q, i) => countChanges(q.original, lastCompared[i] || {})),
    extraction_source: quotes.map((q) => q.source),
  }));
})();
