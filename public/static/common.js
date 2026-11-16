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

  document.addEventListener("DOMContentLoaded", () => {
    const p = document.getElementById("print");
    if (p) p.addEventListener("click", () => window.print());
    setupFeedback(); setupDelete();
  });
  return { postJSON, php, num, store, setupShare };
})();
