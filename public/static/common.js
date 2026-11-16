// Shared helpers: JSON requests, number formatting, print, feedback, sharing, deletion.
const HSP = (() => {
  async function postJSON(url, body) {
    const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    let data = null;
    try { data = await r.json(); } catch (_) { /* empty */ }
    if (!r.ok) throw new Error((data && (typeof data.detail === "string" ? data.detail : "Please check the figures entered.")) || "Request failed");
    return data;
  }
  const php = (x) => (x === null || x === undefined) ? "-" : "PHP " + Math.round(x).toLocaleString("en-PH");
  const num = (x, d = 1) => (x === null || x === undefined) ? "-" : Number(x).toLocaleString("en-PH", { minimumFractionDigits: d, maximumFractionDigits: d });
  const store = {
    get(k) { try { return JSON.parse(sessionStorage.getItem(k)); } catch (_) { return null; } },
    set(k, v) { try { sessionStorage.setItem(k, JSON.stringify(v)); } catch (_) { /* private mode */ } },
  };

  function setupShare(getPayload) {
    const box = document.getElementById("share-consent"), btn = document.getElementById("share-btn"), out = document.getElementById("share-result");
    if (!box) return;
    box.addEventListener("change", () => { btn.disabled = !box.checked; });
    btn.addEventListener("click", async () => {
      const payload = getPayload();
      if (!payload) { out.textContent = "Nothing to share yet."; return; }
      btn.disabled = true; out.textContent = "Sharing...";
      try {
        const r = await postJSON("/api/share", { consent: true, ...payload });
        out.innerHTML = "Thank you. Your reference code is <strong></strong>. Keep it if you may want to delete these figures later (on the About page).";
        out.querySelector("strong").textContent = r.ref_code;
      } catch (e) { out.textContent = e.message; btn.disabled = false; }
    });
  }

  function setupFeedback() {
    const fb = document.getElementById("feedback");
    if (!fb) return;
    let useful = null;
    const send = async () => {
      try {
        await postJSON("/api/feedback", { page: fb.dataset.page.slice(0, 40), useful,
          comment: (document.getElementById("fb-comment").value || "").slice(0, 500) || null,
          website: document.getElementById("fb-website").value || null });
      } catch (_) { /* ignore */ }
      document.getElementById("fb-more").hidden = true;
      document.getElementById("fb-thanks").hidden = false;
    };
    fb.querySelectorAll("[data-useful]").forEach((b) => b.addEventListener("click", () => {
      useful = b.dataset.useful === "true";
      fb.querySelectorAll("[data-useful]").forEach((x) => { x.disabled = true; });
      document.getElementById("fb-more").hidden = false;
    }));
    document.getElementById("fb-send").addEventListener("click", send);
  }

  function setupDelete() {
    const btn = document.getElementById("del-btn");
    if (!btn) return;
    btn.addEventListener("click", async () => {
      const out = document.getElementById("del-result");
      const code = document.getElementById("del-code").value.trim();
      if (!code) { out.textContent = "Enter your reference code."; return; }
      try {
        const r = await postJSON("/api/share/delete", { ref_code: code });
        out.textContent = r.deleted ? "Deleted." : "No shared figures found for that code.";
      } catch (e) { out.textContent = e.message; }
    });
  }

  // ---------- dialogs: "pending feature" and leaving the page ----------
  function dialog(title, paragraphs, buttons) {
    const d = document.createElement("dialog");
    d.className = "modal";
    const h = document.createElement("h2"); h.textContent = title; d.appendChild(h);
    paragraphs.forEach((t) => { const p = document.createElement("p"); p.textContent = t; d.appendChild(p); });
    const row = document.createElement("div"); row.className = "modal-actions";
    buttons.forEach(([label, primary, fn]) => {
      const b = document.createElement("button"); b.type = "button"; b.className = "btn" + (primary ? " primary" : "");
      b.textContent = label;
      b.addEventListener("click", () => { d.close(); d.remove(); if (fn) fn(); });
      row.appendChild(b);
    });
    d.appendChild(row);
    d.addEventListener("cancel", () => d.remove());   // Esc key
    document.body.appendChild(d);
    d.showModal();
    return d;
  }

  function pendingFeature(onContinue) {
    const buttons = [["OK", true, null]];
    if (onContinue) buttons.push(["Continue leaving", false, onContinue]);
    dialog("Pending feature", [
      "A list of accredited installers in your area is not available yet in this test version.",
      "It is planned for a later version. Thank you for your interest.",
    ], buttons);
  }

  let leaving = false;
  /** Warn before leaving. opts.hasData(): unsaved work on the page; opts.askInstallers: offer the installer list once. */
  function guardLeave(opts) {
    const asked = () => store.get("hsp_installers_asked") === true;
    window.addEventListener("beforeunload", (e) => {
      if (leaving || !opts.hasData()) return;
      e.preventDefault(); e.returnValue = "";   // browsers show their own "Leave site?" message
    });
    document.addEventListener("click", (e) => {
      const a = e.target.closest("a[href]");
      if (!a || leaving || e.defaultPrevented || e.ctrlKey || e.metaKey || e.shiftKey || a.target === "_blank") return;
      const url = new URL(a.href, location.href);
      if (url.origin !== location.origin || (url.pathname === location.pathname && url.hash)) return;
      const ask = opts.askInstallers && !asked();
      const data = opts.hasData();
      if (!ask && !data) return;
      e.preventDefault();
      const go = () => { leaving = true; location.href = url.href; };
      const lost = data ? ["If you leave, the quotes and comparison on this page will be lost (nothing is saved)."] : [];
      if (ask) {
        dialog("Before you go", ["Would you like a list of accredited installers in your area?", ...lost], [
          ["Yes, show me", true, () => { store.set("hsp_installers_asked", true); pendingFeature(go); }],
          ["No, leave page", false, () => { store.set("hsp_installers_asked", true); go(); }],
          ["Stay on this page", false, null],
        ]);
      } else {
        dialog("Leave this page?", lost, [["Stay on this page", true, null], ["Leave page", false, go]]);
      }
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    const p = document.getElementById("print");
    if (p) p.addEventListener("click", () => window.print());
    document.querySelectorAll("[data-installers]").forEach((b) => b.addEventListener("click", () => pendingFeature(null)));
    setupFeedback(); setupDelete();
  });
  return { postJSON, php, num, store, setupShare, guardLeave, pendingFeature };
})();
