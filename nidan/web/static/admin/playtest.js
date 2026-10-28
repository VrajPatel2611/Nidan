/**
 * Playtest Static JS (BUILD_PLAN T-022)
 *
 * Holds the playtest's event log — the only copy there is. Every action posts
 * the log to the server, which appends to it, re-runs the assessment engine and
 * returns the new log with both panels rendered. Reset empties the log and asks
 * for the panels again, without leaving the page.
 */

document.addEventListener("DOMContentLoaded", function () {
  const root = document.getElementById("pt-root");
  if (!root) return;

  const base = root.dataset.base;
  const errorEl = document.getElementById("pt-error");
  let events = [];

  function render(data) {
    events = data.events;
    document.getElementById("pt-student").innerHTML = data.student_html;
    document.getElementById("pt-panel").innerHTML = data.instrumentation_html;
    const transcript = document.getElementById("pt-transcript");
    if (transcript) transcript.scrollTop = transcript.scrollHeight;
  }

  async function send(path, body) {
    errorEl.textContent = "";
    root.classList.add("pt-busy");
    try {
      const res = await fetch(`${base}/${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(Object.assign({ events: events }, body || {})),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const err = data.error;
        errorEl.textContent = (err && err.message) || err || "Something went wrong.";
        return false;
      }
      render(data);
      return true;
    } catch (e) {
      errorEl.textContent = "Could not reach the server.";
      return false;
    } finally {
      root.classList.remove("pt-busy");
    }
  }

  document.getElementById("pt-ask").addEventListener("submit", async function (e) {
    e.preventDefault();
    const input = document.getElementById("pt-question");
    const message = input.value.trim();
    if (!message) return;
    if (await send("ask", { message: message })) input.value = "";
    input.focus();
  });

  document.getElementById("pt-diagnose").addEventListener("submit", async function (e) {
    e.preventDefault();
    const input = document.getElementById("pt-diagnosis");
    const text = input.value.trim();
    if (!text) return;
    if (await send("diagnose", { text: text })) input.value = "";
  });

  [["pt-exam", "examine"], ["pt-test", "investigate"]].forEach(function (pair) {
    const select = document.getElementById(pair[0]);
    select.addEventListener("change", async function () {
      if (!select.value) return;
      await send(pair[1], { key: select.value });
      select.value = "";
    });
  });

  document.getElementById("pt-reset").addEventListener("click", function () {
    events = [];
    send("state", {});
  });
});
