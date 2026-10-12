/* =====================================================================
   countdown.js: shown on the birthday person's link before midnight.
   When the timer hits zero the page reloads; the server then sends the
   wall instead of this page.
   ===================================================================== */

const revealAt = new Date(document.querySelector(".countdown").dataset.revealAt);
const el = {
  days: document.getElementById("cd-days"),
  hours: document.getElementById("cd-hours"),
  mins: document.getElementById("cd-mins"),
  secs: document.getElementById("cd-secs"),
};

document.getElementById("cd-when").textContent =
  "Opens " + revealAt.toLocaleString(undefined, {
    weekday: "long", day: "numeric", month: "long", hour: "numeric", minute: "2-digit",
  }) + " your time.";

function tick() {
  const ms = revealAt - Date.now();
  if (ms <= 0) {
    // Small delay so the server clock has definitely passed reveal_at too
    setTimeout(() => location.reload(), 1500);
    clearInterval(timer);
    return;
  }
  const s = Math.floor(ms / 1000);
  el.days.textContent = Math.floor(s / 86400);
  el.hours.textContent = String(Math.floor((s % 86400) / 3600)).padStart(2, "0");
  el.mins.textContent = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
  el.secs.textContent = String(s % 60).padStart(2, "0");
}

const timer = setInterval(tick, 1000);
tick();
