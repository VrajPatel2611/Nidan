/**
 * Review Form Static JS (BUILD_PLAN T-023)
 *
 * Disables Approve while any dimension is below the floor and names which,
 * requires a comment to request changes or reject, and posts the review as
 * JSON so the Playtest beside it keeps its consultation. The server checks
 * every rule again.
 */

document.addEventListener("DOMContentLoaded", function () {
  const card = document.getElementById("rv-form-card");
  if (!card) return;

  const versionId = card.dataset.version;
  const floor = parseInt(card.dataset.floor, 10);
  const form = document.getElementById("rv-form");

  function scores() {
    const out = {};
    const short = [];
    let unanswered = 0;
    form.querySelectorAll("table tr").forEach(function (row) {
      const checked = row.querySelector("input[type=radio]:checked");
      const any = row.querySelector("input[type=radio]");
      if (!checked) { unanswered += 1; return; }
      const value = parseInt(checked.value, 10);
      out[checked.name] = value;
      if (value < floor) short.push(`${any.dataset.label} (${value})`);
    });
    return { values: out, short: short, unanswered: unanswered };
  }

  function refresh() {
    const s = scores();
    const approve = document.getElementById("rv-approve");
    const note = document.getElementById("rv-note");
    const ok = s.unanswered === 0 && s.short.length === 0;
    approve.disabled = !ok;
    approve.style.opacity = ok ? "1" : "0.5";
    if (s.unanswered) {
      note.textContent = `Score all four dimensions (${s.unanswered} left).`;
    } else if (s.short.length) {
      note.textContent = `Approve needs every dimension at ${floor} or above. Below: ${s.short.join(", ")}.`;
    } else {
      note.textContent = "";
    }
  }

  async function post(url, body) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    const data = await res.json().catch(() => ({}));
    const err = data.error;
    return { ok: res.ok, data: data, error: (err && err.message) || err };
  }

  if (form) {
    form.addEventListener("change", refresh);
    refresh();

    form.querySelectorAll("button[data-decision]").forEach(function (button) {
      button.addEventListener("click", async function () {
        const result = document.getElementById("rv-result");
        const decision = button.dataset.decision;
        const comments = document.getElementById("rv-comments").value.trim();
        const s = scores();
        if (s.unanswered) { result.textContent = "Score all four dimensions first."; return; }
        if (decision !== "approved" && !comments) {
          result.textContent = "Add a comment saying what the author should change.";
          return;
        }
        const r = await post(`/admin/reviews/${versionId}/record`,
                             { decision: decision, scores: s.values, comments: comments });
        if (!r.ok) { result.textContent = r.error || "The review could not be recorded."; return; }
        window.location.reload();
      });
    });
  }

  const publish = document.getElementById("rv-publish");
  if (publish) {
    publish.addEventListener("click", async function () {
      const result = document.getElementById("rv-publish-result");
      const r = await post(`/admin/reviews/${versionId}/publish`);
      if (!r.ok) { result.textContent = r.error || "The version could not be published."; return; }
      result.style.color = "#86efac";
      result.textContent = "Published.";
      publish.disabled = true;
    });
  }
});
