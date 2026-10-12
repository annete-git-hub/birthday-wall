/* =====================================================================
   create.js: home page. Log in / register, create walls, and manage
   existing walls (links, lock, theme, hide wishes, delete).
   ===================================================================== */

const $ = (sel) => document.querySelector(sel);

const views = { guest: $("#view-guest"), organizer: $("#view-organizer") };
let currentWallId = null;

// ------------------------------------------------------------------ boot
init();

async function init() {
  try {
    const me = await api("GET", "/api/auth/me");
    showOrganizer(me);
  } catch {
    showGuest();
  }
}

function showGuest() {
  views.organizer.hidden = true;
  views.guest.hidden = false;
  $("#topbar-user").hidden = true;
}

function showOrganizer(user) {
  views.guest.hidden = true;
  views.organizer.hidden = false;
  $("#topbar-user").hidden = false;
  $("#user-name").textContent = user.full_name;

  // Birthday must be tomorrow or later
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  $("#form-create [name=birthday_date]").min = toISODate(tomorrow);

  loadWalls();
}

function toISODate(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// ------------------------------------------------------------------ auth
const tabLogin = $("#tab-login");
const tabRegister = $("#tab-register");
const formLogin = $("#form-login");
const formRegister = $("#form-register");

function selectTab(which) {
  const login = which === "login";
  tabLogin.setAttribute("aria-selected", String(login));
  tabRegister.setAttribute("aria-selected", String(!login));
  formLogin.hidden = !login;
  formRegister.hidden = login;
}
tabLogin.addEventListener("click", () => selectTab("login"));
tabRegister.addEventListener("click", () => selectTab("register"));

formLogin.addEventListener("submit", (e) => submitAuth(e, "/api/auth/login"));
formRegister.addEventListener("submit", (e) => submitAuth(e, "/api/auth/register"));

async function submitAuth(e, url) {
  e.preventDefault();
  const form = e.currentTarget;
  const button = form.querySelector("button[type=submit]");
  setFormError(form, "");
  button.disabled = true;
  try {
    const user = await api("POST", url, Object.fromEntries(new FormData(form)));
    form.reset();
    showOrganizer(user);
  } catch (err) {
    setFormError(form, err.message);
  } finally {
    button.disabled = false;
  }
}

$("#logout-btn").addEventListener("click", async () => {
  await api("POST", "/api/auth/logout").catch(() => {});
  showGuest();
});

// ------------------------------------------------------------------ create wall
const formCreate = $("#form-create");

formCreate.addEventListener("submit", async (e) => {
  e.preventDefault();
  const button = formCreate.querySelector("button[type=submit]");
  setFormError(formCreate, "");
  const data = Object.fromEntries(new FormData(formCreate));
  if (!data.birthday_person_name.trim()) return setFormError(formCreate, "Enter the birthday person's name.");
  if (!data.birthday_date) return setFormError(formCreate, "Pick their birthday.");

  button.disabled = true;
  try {
    const wall = await api("POST", "/api/walls", data);
    formCreate.hidden = true;
    $("#created").hidden = false;
    $("#created-title").textContent = `${wall.birthday_person_name}'s wall is ready`;
    $("#created-contribute").textContent = wall.contribute_url;
    $("#created-reveal").textContent = wall.reveal_url;
    loadWalls();
  } catch (err) {
    setFormError(formCreate, err.message);
  } finally {
    button.disabled = false;
  }
});

$("#create-another").addEventListener("click", () => {
  formCreate.reset();
  formCreate.hidden = false;
  $("#created").hidden = true;
  formCreate.querySelector("input").focus();
});

// ------------------------------------------------------------------ list walls
const STATUS_LABEL = { collecting: "Collecting", revealed: "Opened", locked: "Closed" };

async function loadWalls() {
  const list = $("#walls-list");
  try {
    const walls = await api("GET", "/api/walls");
    if (!walls.length) {
      list.innerHTML = `<p class="empty-state">No walls yet. Start one above and share the link.</p>`;
      return;
    }
    list.innerHTML = walls.map((w) => `
      <article class="wall-row">
        <div>
          <h3>${esc(w.birthday_person_name)}
            <span class="status status-${esc(w.status)}">${esc(STATUS_LABEL[w.status] || w.status)}</span></h3>
          <p class="counts">${formatDate(w.birthday_date)}. ${countsText(w)}</p>
        </div>
        <div class="actions">
          <button class="btn btn-quiet" type="button" data-manage="${w.wall_id}">Manage</button>
        </div>
      </article>`).join("");
  } catch (err) {
    list.innerHTML = `<p class="empty-state">${esc(err.message)}</p>`;
  }
}

function countsText(w) {
  const parts = [`${w.total_wishes} ${w.total_wishes === 1 ? "wish" : "wishes"}`];
  if (w.photos) parts.push(`${w.photos} ${w.photos === 1 ? "photo" : "photos"}`);
  if (w.voice_notes) parts.push(`${w.voice_notes} ${w.voice_notes === 1 ? "voice note" : "voice notes"}`);
  if (w.videos) parts.push(`${w.videos} ${w.videos === 1 ? "video" : "videos"}`);
  return parts.join(", ");
}

$("#walls-list").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-manage]");
  if (btn) openManage(Number(btn.dataset.manage));
});

// ------------------------------------------------------------------ manage dialog
const dialog = $("#manage");

async function openManage(wallId) {
  currentWallId = wallId;
  try {
    const wall = await api("GET", `/api/walls/${wallId}`);
    $("#manage-title").textContent = wall.birthday_person_name;
    $("#manage-meta").textContent =
      `Birthday ${formatDate(wall.birthday_date)}. ${STATUS_LABEL[wall.status] || wall.status}.`;
    $("#manage-contribute").textContent = wall.contribute_url;
    $("#manage-reveal").textContent = wall.reveal_url;
    $("#manage-lock").checked = wall.status === "locked";
    $("#manage-lock").disabled = wall.status === "revealed";

    // Theme lives in MongoDB; hide the controls if it is not configured
    const lookControls = $(".inline-fields");
    try {
      const s = await api("GET", `/api/walls/${wallId}/settings`);
      $("#manage-theme").value = s.theme || "confetti";
      $("#manage-layout").value = s.layout || "masonry";
      lookControls.hidden = false;
    } catch {
      lookControls.hidden = true;
    }

    await loadModeration(wallId);
    if (!dialog.open) dialog.showModal();
  } catch (err) {
    toast(err.message);
  }
}

async function loadModeration(wallId) {
  const list = $("#manage-wishes");
  const wishes = await api("GET", `/api/walls/${wallId}/wishes`);
  if (!wishes.length) {
    list.innerHTML = `<li class="empty-state">No wishes yet. Share the friends link to get started.</li>`;
    return;
  }
  list.innerHTML = wishes.map((w) => {
    const files = w.media.length ? `${w.media.length} ${w.media.length === 1 ? "file" : "files"} attached` : "";
    return `
      <li class="mod-item ${w.is_hidden ? "is-hidden" : ""}">
        <div>
          <span class="who">${esc(w.sender_name)}</span> <span class="muted">(${esc(w.sender_relation)})</span>
          ${w.message_text ? `<p>${esc(truncate(w.message_text, 180))}</p>` : ""}
          ${files ? `<p class="files">${files}</p>` : ""}
        </div>
        <button class="btn btn-quiet" type="button" data-hide="${w.wish_id}" data-hidden="${w.is_hidden}">
          ${w.is_hidden ? "Show" : "Hide"}</button>
      </li>`;
  }).join("");
}

function truncate(text, n) {
  return text.length > n ? text.slice(0, n - 1) + "…" : text;
}

$("#manage-wishes").addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-hide]");
  if (!btn) return;
  const hide = btn.dataset.hidden !== "true";
  btn.disabled = true;
  try {
    await api("PATCH", `/api/walls/${currentWallId}/wishes/${btn.dataset.hide}`, { is_hidden: hide });
    toast(hide ? "Wish hidden" : "Wish shown");
    await loadModeration(currentWallId);
    loadWalls();
  } catch (err) {
    toast(err.message);
    btn.disabled = false;
  }
});

$("#manage-lock").addEventListener("change", async (e) => {
  const locked = e.target.checked;
  try {
    await api("PATCH", `/api/walls/${currentWallId}`, { is_locked: locked });
    toast(locked ? "Wall closed to new wishes" : "Wall open for wishes again");
    loadWalls();
  } catch (err) {
    e.target.checked = !locked;
    toast(err.message);
  }
});

$("#manage-save-look").addEventListener("click", async () => {
  try {
    await api("PUT", `/api/walls/${currentWallId}/settings`, {
      theme: $("#manage-theme").value,
      layout: $("#manage-layout").value,
    });
    toast("Look saved");
  } catch (err) {
    toast(err.message);
  }
});

$("#manage-delete").addEventListener("click", async () => {
  const name = $("#manage-title").textContent;
  if (!confirm(`Delete ${name}'s wall and everything on it? This cannot be undone.`)) return;
  try {
    await api("DELETE", `/api/walls/${currentWallId}`);
    dialog.close();
    toast("Wall deleted");
    loadWalls();
  } catch (err) {
    toast(err.message);
  }
});
