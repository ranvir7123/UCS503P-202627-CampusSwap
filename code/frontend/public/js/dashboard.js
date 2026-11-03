// Student dashboard: current room, the request and its ranked choices, the swap
// chain with confirm / decline and a deadline countdown, and recent activity.
import { api, requireUser } from "./api.js";
import { fillHeader } from "./nav.js";
import { renderMatrix, renderRing, renderSteps, roomDetails } from "./ring.js";
import { $, countdown, formatDateTime, html, ordinal, plural, raw, setBusy, timeAgo, toast, toastError } from "./ui.js";

const root = $("#dash-root");
let data;
let clockTimer;

// Activity rows: chip colour and a short plain name for each kind of event.
const EVENT_TONE = {
  request_submitted: ["chip-info", "Request sent"],
  request_withdrawn: ["chip-neutral", "Withdrawn"],
  match_found: ["chip-warn", "Match found"],
  swap_accepted: ["chip-ok", "Confirmed"],
  cycle_confirmed: ["chip-ok", "All confirmed"],
  cycle_dissolved: ["chip-bad", "Cancelled"],
  swap_approved: ["chip-ok", "Approved"],
};

// How to describe the step a student is on right now (milestone labels are past tense).
const NOW_DOING = {
  submitted: ["Send your ranked list", "Pick up to 5 rooms or room types and send them to join the matching pool."],
  pool: ["Waiting for the next matching round", "Your list is in the pool. Hostel staff run the matching rounds."],
  match: ["Match found", "Check your swap chain below."],
  confirmed: ["Waiting for everyone to confirm", "Every member of the chain must confirm."],
  approved: ["Waiting for warden approval", "Everyone confirmed. The hostel office approves next."],
};

// Icon sizes written out in full so Tailwind keeps the classes.
const ICON_SIZE = { 14: "text-[14px]", 16: "text-[16px]", 18: "text-[18px]", 20: "text-[20px]" };
const icon = (name, size = 18, extra = "") =>
  `<span class="material-symbols-outlined ${ICON_SIZE[size]} ${extra}" aria-hidden="true">${name}</span>`;

function statusChip() {
  const { request, cycle } = data;
  if (!request) return ["chip-neutral", "No request yet"];
  if (request.status === "completed") return ["chip-ok", "Swap approved"];
  if (cycle?.status === "confirmed") return ["chip-ok", "Everyone confirmed"];
  if (cycle) return ["chip-warn", "Waiting for answers"];
  return ["chip-info", "In the matching pool"];
}

function heroCopy() {
  const { request, cycle, room } = data;
  if (!request) return ["No swap request yet", "Pick the rooms you would rather live in and rank them; the next matching round looks for a swap that moves you there."];
  if (request.status === "completed") return ["Your swap is approved", `The warden approved it. Your room is now ${room ? room.label : "updated"}.`];
  if (cycle?.status === "confirmed") return ["Waiting for warden approval", "Everyone in your chain confirmed. The hostel office approves it next, and then the rooms change hands."];
  if (cycle) return ["We found you a swap", `A ${cycle.length}-way chain gives you your ${ordinal(cycle.received_rank)} choice. Everyone must answer before ${formatDateTime(cycle.deadline)}.`];
  return ["You're in the matching pool", "Your ranked list is saved. When hostel staff run the next matching round, your swap chain shows up here."];
}

// "1 day 4 h 12 min left to answer"
function countdownText(iso) {
  const c = countdown(iso);
  if (c.done) return "The time to answer has run out";
  const parts = [];
  if (c.days) parts.push(plural(c.days, "day"));
  if (c.days || c.hours) parts.push(`${c.hours} h`);
  parts.push(`${c.minutes} min`);
  if (!c.days && !c.hours && !c.minutes) return "Less than a minute left to answer";
  return `${parts.join(" ")} left to answer`;
}

function cardTitle(text, right = "") {
  return `<div class="flex items-center justify-between gap-2 mb-3 min-w-0"><span class="text-xs font-medium faint">${text}</span>${right}</div>`;
}

function roomBlock(room) {
  return html`
    <p class="text-base font-semibold text-ink"><span class="font-mono">${room.number}</span></p>
    <p class="text-sm muted mt-0.5 break-words">${room.hostel.name}, block ${room.block}</p>
    <p class="text-xs faint mt-1 break-words">${roomDetails(room)}</p>
    ${room.tags.length ? raw(html`<div class="flex flex-wrap gap-1.5 mt-3">${room.tags.map((t) => raw(html`<span class="chip-neutral max-w-full truncate">${t}</span>`))}</div>`) : ""}`;
}

function typeBlock(pref) {
  return html`
    <p class="text-base font-semibold text-ink break-words">${pref.label}</p>
    <div class="mt-2"><span class="chip-neutral">${raw(icon("category", 14))}Any matching room</span></div>`;
}

function card(inner, extra = "") {
  return `<div class="card card-pad flex flex-col min-w-0 ${extra}">${inner}</div>`;
}

function roomCards() {
  const { room, request, cycle } = data;
  const current = room
    ? card(cardTitle(request?.status === "completed" ? "Your new room" : "Current room", html`<span class="chip-neutral">Seat ${room.seat_label}</span>`) + roomBlock(room))
    : card(cardTitle("Current room") + `<p class="text-base font-semibold text-ink">No room allocated</p><p class="text-sm muted mt-1">You need an allocated room before you can swap. Contact the hostel office.</p>`);

  let target;
  if (cycle) {
    target = card(cardTitle("You move into", html`<span class="${raw(cycle.status === "proposed" ? "chip-warn" : "chip-ok")}">Your ${ordinal(cycle.received_rank)} choice</span>`) + roomBlock(cycle.receive_room));
  } else if (request && request.status !== "completed" && request.preferences.length) {
    const top = request.preferences[0];
    target = card(cardTitle("Your top choice", html`<span class="chip-neutral">1 of ${request.preferences.length}</span>`)
      + (top.kind === "type" || !top.room ? typeBlock(top) : roomBlock(top.room)));
  } else if (request?.status === "completed") {
    target = card(cardTitle("Want another change?") + `<p class="text-base font-semibold text-ink">Start a new request</p><p class="text-sm muted mt-1">You can ask for another swap at any time.</p><a class="btn-secondary self-start mt-4" href="/rooms.html">${icon("search")}Find rooms</a>`);
  } else {
    target = card(cardTitle("Rooms you want") + `<p class="text-base font-semibold text-ink">Nothing picked yet</p><p class="text-sm muted mt-1">You can rank up to 5 exact rooms or room types, best first, and withdraw any time before a match.</p>`);
  }
  return `<div class="grid grid-cols-1 md:grid-cols-3 gap-4">${current}${target}${progressCard()}</div>`;
}

function bar(pct, tone) {
  return `<div class="w-full h-2 rounded-full bg-sunken border border-line overflow-hidden" aria-hidden="true"><div class="h-full ${tone} rounded-full" style="width:${Math.max(0, Math.min(100, pct))}%"></div></div>`;
}

function progressCard() {
  const { cycle, milestones } = data;
  if (cycle && cycle.status === "proposed") {
    const pct = Math.round((cycle.accepted / cycle.length) * 100);
    return card(html`
      ${raw(cardTitle("Time to answer"))}
      <p class="text-base font-semibold text-brass flex items-center gap-2">${raw(icon("schedule", 20))}<span id="countdown" role="timer">${countdownText(cycle.deadline)}</span></p>
      <p class="text-xs faint mt-1">Deadline ${formatDateTime(cycle.deadline)}. If anyone hasn't answered by then, the swap is cancelled.</p>
      <div class="mt-auto pt-5 flex flex-col gap-2">
        <div class="flex justify-between text-xs"><span class="muted">Members confirmed</span><span class="text-ink font-semibold">${cycle.accepted} of ${cycle.length}</span></div>
        ${raw(bar(pct, "bg-ok"))}
      </div>`);
  }
  const done = milestones.filter((m) => m.state === "done").length;
  const current = milestones.find((m) => m.state === "current");
  return card(html`
    ${raw(cardTitle("Your progress"))}
    <p class="text-base font-semibold text-ink">${current ? NOW_DOING[current.key][0] : "All steps done"}</p>
    <p class="text-sm muted mt-1">${current ? NOW_DOING[current.key][1] : "Your swap is complete."}</p>
    <div class="mt-auto pt-5 flex flex-col gap-2">
      <div class="flex justify-between text-xs"><span class="muted">Steps done</span><span class="text-ink font-semibold">${done} of ${milestones.length}</span></div>
      ${raw(bar((done / milestones.length) * 100, "bg-brass"))}
    </div>`);
}

function hero() {
  const [chipClass, chipText] = statusChip();
  const [title, text] = heroCopy();
  const { request, last_run: run } = data;
  const runText = run ? `Last matching round ${timeAgo(run.created_at).replace("Just now", "just now")} · ${run.yield_pct}% of requests matched` : "No matching round has run yet";
  const actions = !request
    ? `<a class="btn-primary" href="/rooms.html">${icon("search")}Find rooms to swap into</a>`
    : (request.status === "open" ? `<button class="btn-secondary" id="btn-withdraw" type="button">${icon("undo")}Withdraw request</button>` : "")
      + `<a class="btn-secondary" href="/rooms.html">${icon("search")}Find rooms</a>`;
  return html`
  <section class="flex flex-col lg:flex-row lg:items-end justify-between gap-4">
    <div class="min-w-0">
      <div class="flex items-center gap-2 flex-wrap mb-3">
        ${request ? raw(html`<span class="chip-neutral font-mono">${request.tracking_id}</span>`) : ""}
        <span class="${raw(chipClass)}">${chipText}</span>
      </div>
      <h1 class="page-title">${title}</h1>
      <p class="muted mt-1.5 max-w-2xl">${text}</p>
      <p class="text-xs faint mt-2">${runText}</p>
    </div>
    <div class="flex items-center gap-2 flex-wrap shrink-0">${raw(actions)}</div>
  </section>`;
}

function chainSection() {
  const { cycle } = data;
  if (!cycle) return "";
  const title = cycle.length === 2 ? "Direct swap" : `${cycle.length}-way swap`;
  return html`
  <section class="card card-pad flex flex-col gap-4 scroll-mt-20" id="swap-chain" aria-labelledby="chain-title">
    <div class="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
      <div class="min-w-0">
        <h2 class="section-title" id="chain-title">${title}</h2>
        <p class="text-sm muted mt-1 max-w-2xl">Each arrow points from a student to the room they move into. Rooms change hands only if every member confirms and the warden approves.</p>
      </div>
      <div class="flex items-center gap-1 p-1 rounded-lg bg-sunken border border-line self-start shrink-0" role="tablist" aria-label="How to show the chain">
        <button aria-selected="true" aria-controls="ring-canvas" class="h-8 px-3 rounded-md text-sm font-medium flex items-center gap-1.5 transition-colors" id="view-graph" role="tab" type="button">${raw(icon("sync_alt", 16))}Swap ring</button>
        <button aria-selected="false" aria-controls="matrix-view" class="h-8 px-3 rounded-md text-sm font-medium flex items-center gap-1.5 transition-colors" id="view-matrix" role="tab" type="button">${raw(icon("table_rows", 16))}Compare rooms</button>
      </div>
    </div>
    <ul class="flex flex-wrap items-center gap-x-5 gap-y-2" id="steps" aria-label="Answers so far"></ul>
    <div class="relative w-full rounded-xl bg-sunken border border-line p-3 sm:p-4 lg:p-0" id="ring-canvas" role="tabpanel" aria-labelledby="view-graph"></div>
    <div class="hidden overflow-x-auto rounded-xl border border-line" id="matrix-view" role="tabpanel" aria-labelledby="view-matrix">
      <table class="w-full text-sm"><thead class="table-head" id="matrix-head"></thead><tbody id="matrix-body"></tbody></table>
    </div>
    <p class="text-xs faint">${cycle.accepted} of ${cycle.length} confirmed · <span class="font-mono">Chain #${cycle.id}</span></p>
  </section>`;
}

function confirmBar() {
  const { cycle } = data;
  if (!cycle || cycle.status !== "proposed") return "";
  if (cycle.my_response === "accepted") {
    const waiting = cycle.length - cycle.accepted;
    return html`
    <div class="notice-ok" role="status">
      ${raw(icon("task_alt", 20, "text-ok shrink-0"))}
      <div><p class="font-semibold text-ink">You confirmed this swap</p>
      <p class="mt-0.5">${waiting ? `Waiting for ${plural(waiting, "more member")} to confirm.` : "Everyone has confirmed."}</p></div>
    </div>`;
  }
  return html`
  <section class="card card-pad border-brass/40 flex flex-col md:flex-row md:items-center justify-between gap-4" aria-labelledby="confirm-title">
    <div class="min-w-0">
      <h2 class="section-title" id="confirm-title">Confirm your swap</h2>
      <p class="text-sm muted mt-1 max-w-2xl break-words">By confirming, you agree to give up ${cycle.give_room.label} and move to ${cycle.receive_room.label} once the warden approves. If anyone declines, the swap is cancelled and the others go back into the pool.</p>
    </div>
    <div class="flex flex-col-reverse sm:flex-row gap-2 shrink-0 w-full sm:w-auto">
      <button class="btn-danger w-full sm:w-auto" id="btn-decline" type="button">${raw(icon("close"))}Decline swap</button>
      <button class="btn-primary w-full sm:w-auto" id="btn-accept" type="button">${raw(icon("check"))}Confirm swap</button>
    </div>
  </section>`;
}

function choicesCard() {
  const { request, cycle } = data;
  if (!request) return "";
  const rows = request.preferences.map((p) => {
    const matched = cycle && p.rank === cycle.received_rank;
    const body = p.kind === "type" || !p.room
      ? html`<p class="text-sm text-ink break-words">${p.label}</p><div class="mt-1.5"><span class="chip-neutral">${raw(icon("category", 14))}Any matching room</span></div>`
      : html`<p class="text-sm text-ink break-words"><span class="font-mono">${p.room.number}</span> <span class="muted">${p.room.hostel.name}, block ${p.room.block}</span></p><p class="text-xs faint mt-0.5 break-words">${roomDetails(p.room)}</p>`;
    return html`
    <li class="flex items-start gap-3 py-3 min-w-0">
      <span class="w-6 h-6 rounded-md bg-raised border border-line text-xs font-semibold text-ink-2 flex items-center justify-center shrink-0" aria-label="Choice ${p.rank}">${p.rank}</span>
      <div class="min-w-0 flex-1">${raw(body)}${matched ? raw(html`<div class="mt-1.5"><span class="${raw(cycle.status === "proposed" ? "chip-warn" : "chip-ok")}">Your match</span></div>`) : ""}</div>
    </li>`;
  }).join("");
  return html`
  <section class="card card-pad" aria-labelledby="choices-title">
    <div class="flex items-center justify-between gap-2 pb-2 border-b border-line">
      <h2 class="section-title" id="choices-title">Your choices</h2>
      <span class="text-xs faint">Best first</span>
    </div>
    <ol class="divide-y divide-line/70">${raw(rows)}</ol>
  </section>`;
}

function stepsCard() {
  const { milestones, room } = data;
  const steps = milestones.map((m) => {
    if (m.state === "done") return html`<li class="flex items-center gap-3 py-2">${raw(icon("check_circle", 20, "text-ok shrink-0"))}<span class="text-sm muted">${m.label}</span></li>`;
    if (m.state === "current") return html`<li class="flex items-start gap-3 py-2" aria-current="step">${raw(icon("radio_button_checked", 20, "text-brass shrink-0"))}<div class="flex flex-col"><span class="text-sm font-semibold text-ink">${NOW_DOING[m.key][0]}</span><span class="text-xs text-brass mt-0.5">You are here</span></div></li>`;
    return html`<li class="flex items-center gap-3 py-2">${raw(icon("radio_button_unchecked", 20, "text-ink-3 shrink-0"))}<span class="text-sm faint">${m.label}</span></li>`;
  }).join("");
  const pending = milestones.filter((m) => m.state !== "done").length;
  return html`
  <section class="card card-pad" aria-labelledby="steps-title">
    <div class="flex items-center justify-between gap-2 pb-2 border-b border-line">
      <h2 class="section-title" id="steps-title">Your steps</h2>
      <span class="${raw(pending ? "chip-neutral" : "chip-ok")}">${pending ? `${pending} to go` : "Complete"}</span>
    </div>
    <ol class="pt-2">${raw(steps)}</ol>
    ${room ? raw(html`<div class="mt-4 pt-4 border-t border-line flex items-center gap-3 min-w-0">${raw(icon("support_agent", 20, "text-ink-3 shrink-0"))}<div class="flex flex-col min-w-0"><span class="text-sm font-medium text-ink truncate">${room.warden}</span><span class="text-xs faint truncate">Warden, ${room.hostel.name}</span></div></div>`) : ""}
  </section>`;
}

function activityCard() {
  const { events } = data;
  const stream = events.length
    ? events.map((e) => {
      const [chip, tag] = EVENT_TONE[e.kind] || ["chip-neutral", "Update"];
      return html`
      <li class="py-3 flex flex-col sm:flex-row sm:items-start gap-1.5 sm:gap-3 min-w-0">
        <span class="${raw(chip)} self-start sm:w-28 justify-center shrink-0">${tag}</span>
        <p class="text-sm muted flex-1 min-w-0 break-words">${e.message}</p>
        <time class="text-xs faint whitespace-nowrap" datetime="${e.created_at}" title="${formatDateTime(e.created_at)}">${timeAgo(e.created_at)}</time>
      </li>`;
    }).join("")
    : `<p class="py-8 text-center text-sm faint">Nothing yet. Your activity will show up here.</p>`;
  return html`
  <section class="card card-pad lg:col-span-2 flex flex-col min-w-0" aria-labelledby="activity-title">
    <div class="flex items-center justify-between gap-2 pb-2 border-b border-line">
      <h2 class="section-title" id="activity-title">Activity</h2>
      <span class="text-xs faint">${plural(events.length, "event")}</span>
    </div>
    ${events.length ? raw(html`<ol class="divide-y divide-line/70 max-h-[28rem] overflow-y-auto">${raw(stream)}</ol>`) : raw(stream)}
  </section>`;
}

function lowerGrid() {
  return `<div class="grid grid-cols-1 lg:grid-cols-3 gap-4 items-start">${activityCard()}<div class="flex flex-col gap-4 min-w-0">${choicesCard()}${stepsCard()}</div></div>`;
}

function tickCountdown() {
  const el = $("#countdown");
  if (!el || !data.cycle) return;
  const text = countdownText(data.cycle.deadline);
  if (el.textContent !== text) el.textContent = text;
}

function render() {
  root.setAttribute("aria-busy", "false");
  root.innerHTML = hero() + roomCards() + chainSection() + confirmBar() + lowerGrid();
  if (data.cycle) {
    renderSteps($("#steps"), data.cycle);
    renderRing($("#ring-canvas"), data.cycle);
    renderMatrix($("#matrix-head"), $("#matrix-body"), data.cycle);
    wireTabs();
  }
  clearInterval(clockTimer);
  if (data.cycle?.status === "proposed") {
    tickCountdown();
    clockTimer = setInterval(tickCountdown, 15000);
  }
  wireActions();
}

function wireTabs() {
  const graph = $("#view-graph"), matrix = $("#view-matrix");
  const on = ["bg-raised", "text-ink"], off = ["text-ink-2", "hover:text-ink"];
  const show = (isGraph) => {
    $("#ring-canvas").hidden = !isGraph;
    $("#matrix-view").classList.toggle("hidden", isGraph);
    for (const [btn, active] of [[graph, isGraph], [matrix, !isGraph]]) {
      btn.classList.remove(...on, ...off);
      btn.classList.add(...(active ? on : off));
      btn.setAttribute("aria-selected", String(active));
    }
  };
  graph.addEventListener("click", () => show(true));
  matrix.addEventListener("click", () => show(false));
  show(true);
}

async function act(button, label, path, success) {
  const restore = setBusy(button, label);
  try {
    const result = await api(path, { method: path.includes("requests") ? "DELETE" : "POST" });
    toast(...(typeof success === "function" ? success(result) : success));
    await load();
  } catch (error) {
    restore();
    toastError(error);
    await load();
  }
}

function wireActions() {
  const { cycle } = data;
  $("#btn-withdraw")?.addEventListener("click", (e) => {
    if (!confirm("Withdraw your request? You can send a new one later.")) return;
    act(e.currentTarget, "Withdrawing…", "/api/requests/current", ["Request withdrawn", "You're no longer in the matching pool.", { icon: "undo" }]);
  });
  $("#btn-accept")?.addEventListener("click", (e) =>
    act(e.currentTarget, "Confirming…", `/api/cycles/${cycle.id}/accept`, (result) => (result.status === "confirmed"
      ? ["Everyone has confirmed", "The warden approves next. Then the rooms change hands.", { icon: "verified" }]
      : ["Swap confirmed", "Waiting for the other members to confirm.", { icon: "verified" }])));
  $("#btn-decline")?.addEventListener("click", (e) => {
    if (!confirm("Decline this swap? The chain will be cancelled for everyone and your request will close.")) return;
    act(e.currentTarget, "Declining…", `/api/cycles/${cycle.id}/decline`, ["Swap declined", "The chain was cancelled. Your request is closed.", { icon: "block", tone: "error" }]);
  });
}

function showSkeleton() {
  root.setAttribute("aria-busy", "true");
  root.innerHTML = $("#dash-skeleton").innerHTML;
}

async function load() {
  try {
    data = await api("/api/me/dashboard");
    render();
  } catch (error) {
    if (error.status === 401) return location.replace("/");
    clearInterval(clockTimer);
    root.setAttribute("aria-busy", "false");
    root.innerHTML = html`
    <div class="notice-bad" role="alert">
      ${raw(icon("error", 20, "text-bad shrink-0"))}
      <div class="flex flex-col gap-3 min-w-0">
        <div><p class="font-semibold text-ink">Couldn't load your swap</p><p class="mt-0.5 break-words">${error.message || "The server did not answer."} Check your connection and try again.</p></div>
        <button class="btn-secondary btn-sm self-start" id="btn-retry" type="button">${raw(icon("refresh", 16))}Try again</button>
      </div>
    </div>`;
    $("#btn-retry").addEventListener("click", () => { showSkeleton(); load(); });
  }
}

const me = await requireUser("student");
fillHeader(me);
load();
