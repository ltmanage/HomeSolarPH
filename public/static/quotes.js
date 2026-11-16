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

  function showRead(q, data) {   // put an extraction result into an existing card
    const el = q.el;
    el.querySelector(".src").textContent = data.source.startsWith("ai") ? "Read automatically: please check" : "Typed in";
    el.querySelector(".qmsg").textContent = data.message || "";
    const d = el.querySelector(".qtext");
    d.hidden = !data.text; d.querySelector("pre").textContent = data.text || "";
    el.querySelector(".qretry").hidden = !(q.file && data.retry);   // only when the reading service was busy
  }

  async function readFile(file, label) {
    const fd = new FormData();
    fd.append("file", file); fd.append("label", label);
    const r = await fetch("/api/quotes/extract", { method: "POST", body: fd });
    let data = null;
    try { data = await r.json(); } catch (_) { /* not JSON, e.g. a server timeout page */ }
    if (!r.ok || !data) throw new Error((data && data.detail) || "Could not read the file. Please try again or type the figures.");
    return data;
  }

  function addCard(fields, source, message, text, file, retry) {
    if (quotes.length >= MAX) { status.textContent = "You can compare up to 4 quotes."; return; }
    const el = tpl.content.firstElementChild.cloneNode(true);
    const letter = "ABCD"[quotes.length];
    fields.label = fields.label && fields.label !== "Quote" ? fields.label : `Quote ${letter}`;
    fillFields(el, fields);
    const q = { el, source, original: readFields(el), file: file || null };   // file stays in this page only, for "Try reading again"
    showRead(q, { source, message, text, retry });
    el.querySelector(".reread").addEventListener("click", async (ev) => {
      const btn = ev.currentTarget, rs = el.querySelector(".rstatus");
      btn.disabled = true; rs.textContent = "Reading again... this can take up to a minute.";
      try {
        const label = readFields(el).label;
        const data = await readFile(q.file, label);
        if (data.source.startsWith("ai")) { data.fields.label = label; fillFields(el, data.fields); q.original = readFields(el); q.source = data.source; }
        showRead(q, data); rs.textContent = "";
      } catch (e) { rs.textContent = e.message; }
      btn.disabled = false;
    });
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
      const data = await readFile(small, `Quote ${"ABCD"[quotes.length]}`);
      addCard(data.fields, data.source, data.message, data.text, small, data.retry);
      status.textContent = "";
    } catch (e) { status.textContent = e.message; }
  });
  document.getElementById("add-manual").addEventListener("click", () => addCard({}, "manual", "Type the key figures from your quote. Leave blank anything it doesn't state."));

  function td(text, cls) { const c = document.createElement("td"); c.textContent = text; if (cls) c.className = cls; return c; }
  const rng = (a, b, f) => (a === null || a === undefined) ? null : (b === null || b === undefined || a === b) ? f(a) : `${f(a)} – ${f(b)}`;
  const perW = (x) => "PHP " + HSP.num(x, 1);
  const yrs = (x) => HSP.num(x, 1);
  function renderResult(res) {
    const t = document.getElementById("cmp-table");
    t.replaceChildren();
    const e = res.estimate;
    const head = document.createElement("tr");
    head.appendChild(document.createElement("th"));
    const eh = document.createElement("th"); eh.className = "est"; eh.textContent = "App estimate"; head.appendChild(eh);
    res.quotes.forEach((q) => { const th = document.createElement("th"); th.textContent = q.label + (q.installer_name ? ` (${q.installer_name})` : ""); head.appendChild(th); });
    t.appendChild(head);
    const needCheck = e.has_solar_check ? "-" : "Run the solar check";
    // [label, app-estimate value, value for each quote]
    const rows = [
      ["System size (kWp)", rng(e.size_low_kwp, e.size_high_kwp, (x) => HSP.num(x, 1)) ?? needCheck, (q) => HSP.num(q.kwp, 2)],
      ["Size from panels listed (kWp)", "-", (q) => HSP.num(q.kwp_from_panels, 2)],
      ["Price incl. VAT", rng(e.cost_low_php, e.cost_high_php, HSP.php) ?? needCheck, (q) => HSP.php(q.price_incl_vat_php)],
      ["Price per watt", rng(e.price_per_wp_low, e.price_per_wp_high, perW) ?? "-", (q) => q.price_per_wp === null ? "-" : perW(q.price_per_wp)],
      ["Expected output per year (kWh)", e.yearly_gen_kwh === null ? needCheck : HSP.num(e.yearly_gen_kwh, 0), (q) => HSP.num(q.yearly_gen_kwh, 0)],
      ["Price per yearly kWh", rng(e.price_per_yearly_kwh_low, e.price_per_yearly_kwh_high, perW) ?? "-", (q) => q.price_per_yearly_kwh === null ? "-" : perW(q.price_per_yearly_kwh)],
      ["Yearly savings", rng(e.yearly_savings_low, e.yearly_savings_high, HSP.php) ?? needCheck,
        (q) => q.yearly_savings_low === null ? "Run the solar check" : `${HSP.php(q.yearly_savings_low)} – ${HSP.php(q.yearly_savings_high)}`],
      ["Payback (years)", e.payback_low === null ? needCheck : `${yrs(e.payback_low)} – ${e.payback_high === null ? "25+" : yrs(e.payback_high)}`,
        (q) => q.payback_low === null ? "-" : `${yrs(q.payback_low)} – ${q.payback_high === null ? "25+" : yrs(q.payback_high)}`],
      ["Panel + inverter + workmanship warranty (years)", "-", (q) => q.warranty_total_years ?? "-"],
      ["Points to check", "-", (q) => String(q.flags.filter((f) => f.level === "check").length)],
    ];
    rows.forEach(([label, est, fn]) => {
      const tr = document.createElement("tr");
      const th = document.createElement("th"); th.textContent = label; tr.appendChild(th);
      tr.appendChild(td(est, "est"));
      res.quotes.forEach((q) => tr.appendChild(td(fn(q))));
      t.appendChild(tr);
    });
    document.getElementById("cmp-basis").textContent = "App estimate: " + e.basis;
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

  const hasNumbers = (f) => Boolean(f.kwp || f.total_price_php || (f.panel_watt && f.panel_qty));
  document.getElementById("compare").addEventListener("click", async () => {
    const all = quotes.map((q) => ({ q, f: readFields(q.el) }));
    const ready = all.filter((c) => hasNumbers(c.f));
    const blank = all.filter((c) => !hasNumbers(c.f)).map((c) => c.f.label);
    if (!ready.length) {
      status.textContent = "Enter at least the system size or total price for a quote (or try reading the file again) before comparing.";
      return;
    }
    const body = { quotes: ready.map((c) => c.f) };
    if (solar) body.solar = solar; else body.region = document.getElementById("region").value;
    try {
      renderResult(await HSP.postJSON("/api/quotes/compare", body));
      lastCompared = ready;
      status.textContent = blank.length ? `Left out of the comparison (no system size or price yet): ${blank.join(", ")}.` : "";
    } catch (e) { status.textContent = e.message; }
  });

  // Consent to save anonymous quote data: asked once before leaving, if at least one quote has figures.
  let consentAnswered = false;
  const sharePayload = () => {
    const used = lastCompared || quotes.map((q) => ({ q, f: readFields(q.el) })).filter((c) => hasNumbers(c.f));
    return {
      kind: "quotes", solar: solar || null, quotes: used.map((c) => c.f),
      region: solar ? null : document.getElementById("region").value,
      fields_corrected: used.map((c) => countChanges(c.q.original, c.f)),
      extraction_source: used.map((c) => c.q.source),
    };
  };
  const hasFigures = () => quotes.some((q) => hasNumbers(readFields(q.el)));

  HSP.guardLeave({
    hasData: () => quotes.length > 0,
    askInstallers: true,
    consent: {
      needed: () => !consentAnswered && hasFigures(),
      ask: (next) => { consentAnswered = true; HSP.askSaveQuotes(sharePayload, next); },
    },
  });

  HSP.setupShare(() => { if (!lastCompared) return null; consentAnswered = true; return sharePayload(); });
})();
