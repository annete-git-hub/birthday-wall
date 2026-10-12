/* =====================================================================
   wall.js: the birthday person's wall.
   ===================================================================== */

const token = document.querySelector(".wall").dataset.token;
const wishesEl = document.getElementById("wishes");
const EMOJIS = ["❤️", "😂", "🥹", "🎉", "😍", "🙏", "🔥", "👏"];
const COLORS = ["c-pink", "c-blue", "c-yellow", "c-white"];
const RELATION = { friend: "Friend", family: "Family", classmate: "Classmate", colleague: "Colleague", other: "" };

let reactionsEnabled = true;

loadWall();

async function loadWall() {
  try {
    const data = await api("GET", `/api/reveal/${encodeURIComponent(token)}`);
    applySettings(data.settings || {});
    renderStats(data.stats);
    renderWishes(data.wishes);
  } catch (err) {
    if (err.status === 403) return location.reload();   // server shows the countdown
    wishesEl.innerHTML = `<p class="muted">${esc(err.message)}</p>`;
  }
}

// ------------------------------------------------------------------ settings
function applySettings(s) {
  const body = document.body;
  body.className = body.className.replace(/\btheme-\S+|\blayout-\S+/g, "").trim();
  body.classList.add(`theme-${s.theme || "confetti"}`, `layout-${s.layout || "masonry"}`);

  if (s.colors) {
    if (s.colors.background) body.style.setProperty("--paper", s.colors.background);
    if (s.colors.accent) body.style.setProperty("--pink", s.colors.accent);
    if (s.colors.text) body.style.setProperty("--ink", s.colors.text);
  }
  if (s.font) {
    // Load the organizer's chosen Google Font, then use it for headings and messages
    const family = s.font.replace(/[^A-Za-z0-9 ]/g, "");
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = `https://fonts.googleapis.com/css2?family=${encodeURIComponent(family)}:wght@400;600;800&display=swap`;
    document.head.appendChild(link);
    body.style.setProperty("--display", `"${family}", "Bricolage Grotesque", sans-serif`);
  }
  if (s.background_music && s.background_music.url) setupMusic(s.background_music);
}

function setupMusic(music) {
  const btn = document.getElementById("music-btn");
  const audio = document.getElementById("music");
  audio.src = music.url;
  btn.hidden = false;
  btn.addEventListener("click", () => {
    if (audio.paused) { audio.play(); btn.textContent = "Pause music"; }
    else { audio.pause(); btn.textContent = "Play music"; }
  });
}

// ------------------------------------------------------------------ stats line
function plural(n, one, many) { return `${n} ${n === 1 ? one : many}`; }

function renderStats(st) {
  if (!st || !st.total_wishes) return;
  const extras = [];
  if (st.photos) extras.push(plural(st.photos, "photo", "photos"));
  if (st.voice_notes) extras.push(plural(st.voice_notes, "voice note", "voice notes"));
  if (st.videos) extras.push(plural(st.videos, "video", "videos"));
  let text = `${plural(st.total_wishes, "wish", "wishes")} from ${plural(st.unique_senders, "person", "people")}`;
  if (extras.length) {
    const last = extras.pop();
    text += `, with ${extras.length ? extras.join(", ") + " and " : ""}${last}`;
  }
  document.getElementById("wall-stats").textContent = text + ".";
}

// ------------------------------------------------------------------ wishes
function renderWishes(wishes) {
  if (!wishes.length) {
    wishesEl.innerHTML = `<p class="muted" style="text-align:center">No wishes were left on this wall.</p>`;
    return;
  }
  wishesEl.innerHTML = wishes.map(cardHtml).join("");
}

function cardHtml(w, i) {
  // Stable "random" tilt per wish so it does not jump around on reload
  const tilt = (((w.wish_id * 37) % 7) - 3) * 0.55;
  const color = COLORS[i % COLORS.length];
  const long = (w.message_text || "").length > 220 ? " long" : "";
  const rel = RELATION[w.sender_relation] || "";

  return `
    <article class="wish ${color}${long}" style="--tilt:${tilt}deg" data-wish="${w.wish_id}">
      ${w.message_text ? `<p class="wish-text">${esc(w.message_text)}</p>` : ""}
      ${w.media.length ? `<div class="wish-media">${w.media.map(mediaHtml).join("")}</div>` : ""}
      <div class="wish-from">
        <strong>${esc(w.sender_name)}</strong>
        ${rel ? `<small>${rel}</small>` : ""}
      </div>
      <div class="reactions" role="group" aria-label="React to ${esc(w.sender_name)}'s wish">
        ${EMOJIS.map((e) => `<button class="react" type="button" data-emoji="${e}"
             aria-pressed="${w.reactions.includes(e)}" aria-label="React ${e}">${e}</button>`).join("")}
      </div>
    </article>`;
}

function mediaHtml(m) {
  const url = esc(m.url);
  if (m.type === "image") {
    return `<img src="${url}" alt="Photo" loading="lazy" data-zoom>`;
  }
  if (m.type === "video") {
    return `<video src="${url}" controls preload="metadata" playsinline></video>`;
  }
  return `<div class="voice"><small>Voice note${m.duration_seconds ? ", " + formatDuration(m.duration_seconds) : ""}</small>
          <audio src="${url}" controls preload="none"></audio></div>`;
}

// ------------------------------------------------------------------ reactions
wishesEl.addEventListener("click", async (e) => {
  const btn = e.target.closest(".react");
  if (!btn || !reactionsEnabled) return;

  const wishId = btn.closest(".wish").dataset.wish;
  const emoji = btn.dataset.emoji;
  const wasOn = btn.getAttribute("aria-pressed") === "true";
  btn.setAttribute("aria-pressed", String(!wasOn));     // update instantly, undo on error

  try {
    await api(wasOn ? "DELETE" : "POST",
              `/api/reveal/${encodeURIComponent(token)}/wishes/${wishId}/reactions`, { emoji });
  } catch (err) {
    btn.setAttribute("aria-pressed", String(wasOn));
    if (err.status === 503) {
      reactionsEnabled = false;
      document.querySelectorAll(".reactions").forEach((r) => r.remove());
    } else {
      toast(err.message);
    }
  }
});

// ------------------------------------------------------------------ photo lightbox
const lightbox = document.getElementById("lightbox");
wishesEl.addEventListener("click", (e) => {
  const img = e.target.closest("[data-zoom]");
  if (!img) return;
  document.getElementById("lightbox-img").src = img.src;
  lightbox.showModal();
});
lightbox.addEventListener("click", (e) => { if (e.target === lightbox) lightbox.close(); });
