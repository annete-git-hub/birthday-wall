/* =====================================================================
   contribute.js: friends and family leave a wish.
   Text, photos, videos and voice notes recorded in the browser.
   ===================================================================== */

const root = document.querySelector(".contribute");
const token = root.dataset.token;
const form = document.getElementById("wish-form");
const attachList = document.getElementById("attachments");

const MAX_FILES = 5;
const MAX_BYTES = { image: 10 * 1024 * 1024, audio: 20 * 1024 * 1024, video: 50 * 1024 * 1024 };
const MAX_RECORD_SECONDS = 180;

let attachments = [];      // { file, kind, previewUrl }
let personName = "them";

// ------------------------------------------------------------------ load wall
loadWall();

async function loadWall() {
  try {
    const wall = await api("GET", `/api/contribute/${encodeURIComponent(token)}`);
    personName = wall.birthday_person_name;
    document.title = `A wish for ${personName}`;
    document.getElementById("c-title").textContent = `Leave a wish for ${personName}`;
    document.getElementById("c-date").textContent = `Birthday on ${formatDate(wall.birthday_date)}`;
    document.getElementById("c-count").textContent = wall.wish_count
      ? `${wall.wish_count} ${wall.wish_count === 1 ? "wish" : "wishes"} so far. ${personName} sees them all on the day.`
      : `Nobody has posted yet. ${personName} sees every wish on the day.`;

    if (wall.is_open) {
      form.hidden = false;
      try { form.sender_name.value = localStorage.getItem("bw_sender_name") || ""; } catch { /* storage blocked */ }
    } else {
      document.getElementById("closed").hidden = false;
    }
  } catch (err) {
    document.getElementById("c-title").textContent = "This link is not working";
    document.getElementById("c-date").textContent = "";
    document.getElementById("c-count").textContent = err.message;
  }
}

// ------------------------------------------------------------------ message counter
form.message_text.addEventListener("input", () => {
  document.getElementById("char-count").textContent = form.message_text.value.length;
});

// ------------------------------------------------------------------ attachments
function kindOf(mime) {
  const k = (mime || "").split("/")[0];
  return ["image", "audio", "video"].includes(k) ? k : null;
}

function addFile(file) {
  setFormError(form, "");
  const kind = kindOf(file.type);
  if (!kind) return setFormError(form, `"${file.name}" is not a photo, video or audio file.`);
  if (attachments.length >= MAX_FILES) return setFormError(form, `You can attach up to ${MAX_FILES} files.`);
  if (file.size > MAX_BYTES[kind]) {
    return setFormError(form, `"${file.name}" is ${formatBytes(file.size)}. The limit for ${kind} is ${formatBytes(MAX_BYTES[kind])}.`);
  }
  attachments.push({ file, kind, previewUrl: kind === "image" ? URL.createObjectURL(file) : null });
  renderAttachments();
}

function renderAttachments() {
  const icons = { audio: "🎙️", video: "🎬" };
  attachList.innerHTML = attachments.map((a, i) => `
    <li>
      ${a.previewUrl
        ? `<img class="thumb" src="${a.previewUrl}" alt="">`
        : `<span class="thumb" aria-hidden="true">${icons[a.kind]}</span>`}
      <span class="name">${esc(a.file.name)}<small>${a.kind}, ${formatBytes(a.file.size)}</small></span>
      <button class="btn btn-quiet" type="button" data-remove="${i}" aria-label="Remove ${esc(a.file.name)}">Remove</button>
    </li>`).join("");
}

attachList.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-remove]");
  if (!btn) return;
  const [removed] = attachments.splice(Number(btn.dataset.remove), 1);
  if (removed.previewUrl) URL.revokeObjectURL(removed.previewUrl);
  renderAttachments();
});

document.getElementById("file-input").addEventListener("change", (e) => {
  [...e.target.files].forEach(addFile);
  e.target.value = "";     // allow picking the same file again later
});

// ------------------------------------------------------------------ voice recorder
const recordBtn = document.getElementById("record-btn");
const recorderBox = document.getElementById("recorder");
const recTime = document.getElementById("rec-time");
let recorder = null, recChunks = [], recTimer = null, recSeconds = 0, recCancelled = false;

if (!navigator.mediaDevices || !window.MediaRecorder) {
  recordBtn.hidden = true;   // very old browser: they can still upload an audio file
}

recordBtn.addEventListener("click", async () => {
  setFormError(form, "");
  if (attachments.length >= MAX_FILES) return setFormError(form, `You can attach up to ${MAX_FILES} files.`);

  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch {
    return setFormError(form, "Microphone access was blocked. Allow it in your browser settings, or upload an audio file instead.");
  }

  const mimeType = ["audio/webm", "audio/mp4", "audio/ogg"].find((t) => MediaRecorder.isTypeSupported(t)) || "";
  recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
  recChunks = [];
  recCancelled = false;
  recSeconds = 0;
  recTime.textContent = "0:00";

  recorder.addEventListener("dataavailable", (ev) => ev.data.size && recChunks.push(ev.data));
  recorder.addEventListener("stop", () => {
    stream.getTracks().forEach((t) => t.stop());
    clearInterval(recTimer);
    recorderBox.hidden = true;
    recordBtn.hidden = false;
    if (recCancelled || !recChunks.length) return;
    // Strip codec parameters ("audio/webm;codecs=opus" -> "audio/webm")
    const type = (recorder.mimeType || "audio/webm").split(";")[0];
    const ext = type.split("/")[1] === "mp4" ? "m4a" : type.split("/")[1];
    addFile(new File(recChunks, `voice-note-${formatDuration(recSeconds).replace(":", "m")}s.${ext}`, { type }));
  });

  recorder.start();
  recordBtn.hidden = true;
  recorderBox.hidden = false;
  recTimer = setInterval(() => {
    recSeconds += 1;
    recTime.textContent = formatDuration(recSeconds);
    if (recSeconds >= MAX_RECORD_SECONDS) recorder.stop();
  }, 1000);
});

document.getElementById("rec-stop").addEventListener("click", () => recorder?.stop());
document.getElementById("rec-cancel").addEventListener("click", () => {
  recCancelled = true;
  recorder?.stop();
});

// ------------------------------------------------------------------ submit
form.addEventListener("submit", (e) => {
  e.preventDefault();
  setFormError(form, "");

  const name = form.sender_name.value.trim();
  const message = form.message_text.value.trim();
  if (!name) return setFormError(form, "Add your name so they know who it is from.");
  if (!message && !attachments.length) return setFormError(form, "Write a message or attach a photo, video or voice note.");
  if (recorder && recorder.state === "recording") return setFormError(form, "Stop the voice recording first.");

  const data = new FormData();
  data.append("sender_name", name);
  data.append("sender_relation", form.sender_relation.value);
  data.append("message_text", message);
  attachments.forEach((a) => data.append("files", a.file, a.file.name));

  try { localStorage.setItem("bw_sender_name", name); } catch { /* storage blocked */ }
  send(data);
});

/* XMLHttpRequest instead of fetch() because it reports upload progress,
   which matters for a 50 MB video on a phone connection. */
function send(data) {
  const sendBtn = document.getElementById("send-btn");
  const progress = document.getElementById("progress");
  const bar = document.getElementById("progress-bar");

  sendBtn.disabled = true;
  sendBtn.textContent = attachments.length ? "Uploading…" : "Sending…";
  progress.hidden = !attachments.length;
  bar.style.width = "0";

  const xhr = new XMLHttpRequest();
  xhr.open("POST", `/api/contribute/${encodeURIComponent(token)}/wishes`);
  xhr.upload.addEventListener("progress", (ev) => {
    if (ev.lengthComputable) bar.style.width = `${Math.round((ev.loaded / ev.total) * 100)}%`;
  });
  xhr.addEventListener("load", () => {
    let body = {};
    try { body = JSON.parse(xhr.responseText); } catch { /* non-JSON error page */ }
    reset();
    if (xhr.status === 201) {
      form.hidden = true;
      document.getElementById("sent").hidden = false;
      document.getElementById("sent-text").textContent =
        `${personName} will see it when the wall opens on their birthday.`;
    } else if (xhr.status === 410) {
      form.hidden = true;
      document.getElementById("closed").hidden = false;
    } else if (xhr.status === 413) {
      setFormError(form, "Those files are too large to send together. Remove one and try again.");
    } else {
      setFormError(form, body.error || "Something went wrong. Please try again.");
    }
  });
  xhr.addEventListener("error", () => {
    reset();
    setFormError(form, "Could not reach the server. Check your connection and try again.");
  });
  xhr.send(data);

  function reset() {
    sendBtn.disabled = false;
    sendBtn.textContent = "Send wish";
    progress.hidden = true;
  }
}

document.getElementById("send-another").addEventListener("click", () => {
  const savedName = form.sender_name.value;
  form.reset();
  form.sender_name.value = savedName;
  attachments.forEach((a) => a.previewUrl && URL.revokeObjectURL(a.previewUrl));
  attachments = [];
  renderAttachments();
  document.getElementById("char-count").textContent = "0";
  document.getElementById("sent").hidden = true;
  form.hidden = false;
  form.message_text.focus();
});
