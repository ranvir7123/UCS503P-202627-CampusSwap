// Login page: sign in as a student, hostel staff or faculty; quiet live numbers beside the form.
import { api, homeFor } from "./api.js";
import { $, $$, html, raw, plural, setBusy } from "./ui.js";

const DOMAIN = "@thapar.edu";
const PASSWORD = "campus123";
const ROLES = ["student", "admin", "faculty"];
const DEMO = { student: "student1@thapar.edu", admin: "warden@thapar.edu", faculty: "faculty1@thapar.edu" };
// Tab names as the server writes them in the "wrong_role" message.
const TAB_NAMES = { student: "student", "hostel staff": "admin", faculty: "faculty" };
const COPY = {
  student: { desc: "Use your Thapar email to rank rooms and follow your swap.", placeholder: "yourname_be24@thapar.edu" },
  admin: { desc: "Run matching rounds and approve swaps everyone has confirmed.", placeholder: "warden@thapar.edu" },
  faculty: { desc: "Use your Thapar email to swap weekly lecture slots.", placeholder: "yourname@thapar.edu" },
};
const TAB_ON = ["bg-raised", "text-ink"];
const TAB_OFF = ["text-ink-3", "hover:text-ink"];

let role = "student";
const email = $("#campus-identity");
const password = $("#password");
const notice = $("#form-notice");
const tabs = $$("[role=tab]");

// ---------------------------------------------------------------- role tabs
function switchRole(next, { focus = false, keepNotice = false } = {}) {
  role = next;
  for (const tab of tabs) {
    const on = tab.dataset.role === role;
    tab.setAttribute("aria-selected", String(on));
    tab.tabIndex = on ? 0 : -1;
    tab.classList.remove(...(on ? TAB_OFF : TAB_ON));
    tab.classList.add(...(on ? TAB_ON : TAB_OFF));
    if (on) {
      $("#auth-form").setAttribute("aria-labelledby", tab.id);
      if (focus) tab.focus();
    }
  }
  $("#panel-desc").textContent = COPY[role].desc;
  email.placeholder = COPY[role].placeholder;
  if (!keepNotice) showNotice(null);
}

function onTabKey(event) {
  const index = ROLES.indexOf(role);
  const moves = { ArrowRight: index + 1, ArrowLeft: index - 1, Home: 0, End: ROLES.length - 1 };
  if (!(event.key in moves)) return;
  event.preventDefault();
  switchRole(ROLES[(moves[event.key] + ROLES.length) % ROLES.length], { focus: true });
}

// ---------------------------------------------------------------- email helper
function checkDomain() {
  const v = email.value.trim().toLowerCase();
  const indicator = $("#domain-indicator");
  let tone = "faint", icon = "mail", text = `Must end with ${DOMAIN}`;
  if (v.endsWith(DOMAIN) && v.length > DOMAIN.length) {
    tone = "text-ok"; icon = "check_circle"; text = "Thapar email";
  } else if (v.length > 5 && v.includes("@")) {
    tone = "text-bad"; icon = "error"; text = `Does not end with ${DOMAIN}`;
  }
  indicator.className = `flex items-center gap-1.5 text-xs min-w-0 ${tone}`;
  indicator.innerHTML = html`<span class="material-symbols-outlined text-[16px]" aria-hidden="true">${icon}</span><span class="truncate">${text}</span>`;
}

function addDomain() {
  const local = email.value.split("@")[0].trim();
  email.value = `${local}${DOMAIN}`;
  email.focus();
  email.setSelectionRange(0, local.length);
  checkDomain();
}

// ---------------------------------------------------------------- notice
function showNotice(kind, title = "", message = "") {
  if (!kind) {
    notice.innerHTML = "";
    return;
  }
  const look = { bad: ["notice-bad", "error", "text-bad"], ok: ["notice-ok", "check_circle", "text-ok"] }[kind];
  notice.innerHTML = html`<div class="${look[0]}" role="${kind === "bad" ? "alert" : "status"}">
    <span class="material-symbols-outlined text-[20px] ${look[2]} shrink-0" aria-hidden="true">${look[1]}</span>
    <div class="min-w-0">
      <p class="font-semibold text-ink">${title}</p>
      ${message ? raw(html`<p class="mt-0.5 break-words">${message}</p>`) : ""}
    </div>
  </div>`;
}

const ERROR_TITLES = {
  not_institute_email: "Use your Thapar email",
  bad_credentials: "Wrong email or password",
  too_many_attempts: "Too many tries",
  network: "Can't reach the server",
};

// ---------------------------------------------------------------- sign in
async function submit(event) {
  event.preventDefault();
  const address = email.value.trim().toLowerCase();
  if (!address.endsWith(DOMAIN) || address.length <= DOMAIN.length) {
    showNotice("bad", "Use your Thapar email", `Your email must end with ${DOMAIN}.`);
    email.focus();
    return;
  }
  if (!password.value) {
    showNotice("bad", "Enter your password", "The password box is empty.");
    password.focus();
    return;
  }
  showNotice(null);
  const restore = setBusy($("#btn-submit"), "Signing in…");
  try {
    const me = await api("/api/auth/login", { method: "POST", body: { email: address, password: password.value, role } });
    showNotice("ok", `Signed in as ${me.name}`, "Opening your page…");
    location.assign(homeFor(me.role));
  } catch (error) {
    restore();
    if (error.code === "wrong_role") {
      const match = /belongs on the (.+?) tab/i.exec(error.message || "");
      const target = match && TAB_NAMES[match[1].toLowerCase()];
      if (target) switchRole(target, { keepNotice: true });
      const tabName = target ? $(`[data-role=${target}]`).textContent : "other";
      showNotice("bad", `Switched to the ${tabName} tab`, `${error.message} Press Sign in again.`);
      return;
    }
    showNotice("bad", ERROR_TITLES[error.code] || "Couldn't sign you in", error.message);
  }
}

function useDemo(which) {
  switchRole(which);
  email.value = DEMO[which];
  password.value = PASSWORD;
  checkDomain();
  $("#btn-submit").focus();
}

// ---------------------------------------------------------------- live numbers
function setStat(name, value, sub) {
  const el = $(`[data-stat=${name}]`);
  el.className = "text-2xl font-bold text-ink tabular-nums";
  el.textContent = value;
  $(`[data-stat=${name}-sub]`).textContent = sub;
}

function drawSparkline(counts) {
  const max = Math.max(1, ...counts);
  const step = 300 / (counts.length - 1);
  const d = counts.map((v, i) => `${i ? "L" : "M"}${(i * step).toFixed(1)} ${(56 - (v / max) * 52).toFixed(1)}`).join(" ");
  $("#spark-line").setAttribute("d", d);
  $("#spark-box").classList.remove("skeleton");
  $("#spark-svg").removeAttribute("hidden");
  $("#spark-text").textContent = `Requests per day, oldest first: ${counts.join(", ")}.`;
}

async function loadStats() {
  const box = $("#stats");
  try {
    const s = await api("/api/public/stats");
    setStat("open", s.open_requests.toLocaleString("en-IN"), "Waiting in the matching pool");
    setStat("rooms", s.rooms.toLocaleString("en-IN"), `Across ${plural(s.hostels, "hostel")}`);
    if (s.last_run) {
      setStat("yield", `${s.last_run.yield_pct}%`, `${s.last_run.matched} of ${plural(s.last_run.pool_size, "request")} matched`);
    } else {
      setStat("yield", "None yet", "Hostel staff start each round");
      $("[data-stat=yield]").className = "text-base font-semibold text-ink-2 leading-8";
    }
    drawSparkline(s.requests_per_day);
    if (s.timing?.demo) {
      $("#demo-mode-text").textContent = `Demo mode: swaps have ${s.timing.confirm} to confirm.`;
      $("#demo-mode").hidden = false;
    }
  } catch {
    for (const el of box.querySelectorAll("dl, figure")) el.hidden = true;
    $("#stats-error").hidden = false;
  } finally {
    box.setAttribute("aria-busy", "false");
  }
}

// ---------------------------------------------------------------- start
// Already signed in? Go straight to the right page.
api("/api/auth/status")
  .then(({ user }) => {
    if (user) location.replace(homeFor(user.role));
  })
  .catch(() => {});

for (const tab of tabs) {
  tab.addEventListener("click", () => switchRole(tab.dataset.role));
  tab.addEventListener("keydown", onTabKey);
}
email.addEventListener("input", checkDomain);
$("#chip-domain").addEventListener("click", addDomain);
$("#toggle-password").addEventListener("click", () => {
  const show = password.type === "password";
  password.type = show ? "text" : "password";
  $("#toggle-password-icon").textContent = show ? "visibility_off" : "visibility";
  $("#toggle-password").setAttribute("aria-label", show ? "Hide password" : "Show password");
  $("#toggle-password").setAttribute("aria-pressed", String(show));
});
for (const button of $$("[data-demo]")) button.addEventListener("click", () => useDemo(button.dataset.demo));
$("#auth-form").addEventListener("submit", submit);
switchRole("student");
loadStats();
