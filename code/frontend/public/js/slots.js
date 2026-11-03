// Faculty lecture slots: offer one lecture, rank up to 5 better slots, confirm or decline a swap.
import { api, requireUser } from "./api.js";
import { fillHeader } from "./nav.js";
import { $, countdown, formatDateTime, html, plural, raw, setBusy, timeAgo, toast, toastError } from "./ui.js";

const MAX_CHOICES = 5;
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

const statusEl = $("#status");
const builderEl = $("#builder");
const activityEl = $("#activity");

let data = null;
let offeredId = null; // the lecture this teacher wants to move (step 1)
let ranked = []; // slot ids they would prefer, best first (step 2)
let sendError = "";
let clockTimer;

const icon = (name, size = 18, extra = "") =>
  raw(`<span class="material-symbols-outlined text-[${size}px] ${extra}" aria-hidden="true">${name}</span>`);
const hhmm = (min) => `${String(Math.floor(min / 60)).padStart(2, "0")}:${String(min % 60).padStart(2, "0")}`;
const slotTime = (s) => `${hhmm(s.start_min)}–${hhmm(s.end_min)}`;
const slotById = (id) => data.slots.find((s) => s.id === id);

// ---------------------------------------------------------------- shared bits
function responseChip(response) {
  if (response === "accepted") return html`<span class="chip-ok">${icon("check", 14)}Confirmed</span>`;
  if (response === "declined") return html`<span class="chip-bad">${icon("close", 14)}Declined</span>`;
  return html`<span class="chip-warn">${icon("schedule", 14)}Waiting</span>`;
}

function slotBox(title, slot, tone) {
  const border = tone === "new" ? "border-brass/40" : "border-line";
  return html`
  <div class="flex-1 min-w-0 rounded-lg border ${raw(border)} bg-sunken p-3.5">
    <p class="text-xs faint">${title}</p>
    <p class="font-semibold text-ink mt-1 break-words">${slot.time_label}</p>
    <p class="text-sm muted break-words">Hall ${slot.hall}</p>
  </div>`;
}

function moveRow(cycle, firstTitle, secondTitle) {
  return html`
  <div class="flex flex-col sm:flex-row sm:items-stretch gap-2 sm:gap-3 max-w-3xl">
    ${raw(slotBox(firstTitle, cycle.gives, "old"))}
    <div class="flex items-center justify-center text-ink-3 shrink-0">${icon("arrow_forward", 20, "rotate-90 sm:rotate-0")}</div>
    ${raw(slotBox(secondTitle, cycle.receives, "new"))}
  </div>`;
}

function membersList(cycle) {
  const n = cycle.members.length;
  const items = cycle.members.map((m, i) => {
    const gets = cycle.members[(i + 1) % n].gives; // each member takes the next member's slot
    return html`
    <li class="flex items-start gap-3 py-3 first:pt-0 last:pb-0">
      <div class="avatar">${m.initials}</div>
      <div class="min-w-0 flex-1">
        <p class="text-sm font-semibold text-ink break-words">${m.name}${m.is_me ? raw(' <span class="chip-neutral ml-1 align-middle">You</span>') : ""}</p>
        <p class="text-xs faint mt-0.5 break-words">Gives ${m.gives} · gets ${gets}</p>
      </div>
      <div class="shrink-0">${raw(responseChip(m.response))}</div>
    </li>`;
  });
  return html`
  <div>
    <h3 class="text-sm font-semibold text-ink">Everyone in this swap <span class="faint font-normal">(${cycle.accepted} of ${cycle.length} confirmed)</span></h3>
    <ul class="mt-3 divide-y divide-line/70">${raw(items.join(""))}</ul>
  </div>`;
}

function deadlineText(iso) {
  const c = countdown(iso);
  if (c.done) return "The deadline has passed.";
  const parts = c.days ? [plural(c.days, "day"), `${c.hours} h`] : c.hours ? [`${c.hours} h`, `${c.minutes} min`] : [`${Math.max(c.minutes, 1)} min`];
  return `${parts.join(" ")} left to answer`;
}

function deadlineRow(cycle) {
  return html`
  <div class="flex items-start gap-2.5 text-sm">
    ${icon("schedule", 18, "text-brass mt-0.5")}
    <div>
      <p class="font-semibold text-ink" id="countdown">${deadlineText(cycle.deadline)}</p>
      <p class="text-xs faint mt-0.5">Deadline ${formatDateTime(cycle.deadline)}. If someone has not answered by then, the swap is cancelled and those who confirmed go back into the pool.</p>
    </div>
  </div>`;
}

const myCourse = (slot) => `${slot.course_code} ${slot.course_name}`;

// ---------------------------------------------------------------- status area
function cycleCard(cycle, request) {
  const tracking = request ? html`<span class="font-mono text-xs faint">${request.tracking_id}</span>` : "";
  const size = cycle.length === 2 ? "2-way swap" : `${cycle.length}-way swap`;

  if (cycle.status === "approved") {
    return html`
    <div class="card card-pad flex flex-col gap-5">
      <div class="flex flex-wrap items-center gap-2"><span class="chip-ok">${icon("check_circle", 14)}Approved</span>${raw(tracking)}</div>
      <div>
        <h2 class="section-title">Your lecture slot has changed</h2>
        <p class="muted mt-1 break-words">Staff approved the swap. You now teach ${myCourse(cycle.receives)} on ${cycle.receives.label}.</p>
      </div>
      <div class="rounded-lg border border-ok/30 bg-ok/5 p-3.5 max-w-md">
        <p class="text-xs faint">Your new slot</p>
        <p class="font-semibold text-ink mt-1 break-words">${cycle.receives.time_label}</p>
        <p class="text-sm muted break-words">Hall ${cycle.receives.hall} · ${myCourse(cycle.receives)}</p>
      </div>
      <p class="text-xs faint">Want to move another lecture? Send a new request below.</p>
    </div>`;
  }

  if (cycle.status === "confirmed") {
    return html`
    <div class="card card-pad flex flex-col gap-5">
      <div class="flex flex-wrap items-center gap-2"><span class="chip-ok">${icon("task_alt", 14)}Everyone confirmed</span><span class="chip-neutral">${size}</span>${raw(tracking)}</div>
      <div>
        <h2 class="section-title">Waiting for staff approval</h2>
        <p class="muted mt-1 break-words">Everyone in the swap confirmed. Once staff approve it, your ${myCourse(cycle.gives)} lecture moves to ${cycle.receives.label}.</p>
      </div>
      ${raw(moveRow(cycle, "Now", "After approval"))}
      ${raw(membersList(cycle))}
    </div>`;
  }

  if (cycle.status === "proposed") {
    const pending = cycle.my_response === "pending";
    const waiting = cycle.length - cycle.accepted;
    const intro = pending
      ? html`<h2 class="section-title">A slot swap was found</h2>
        <p class="muted mt-1 break-words">Your ${myCourse(cycle.gives)} lecture would move from ${cycle.gives.label} to ${cycle.receives.label} (your choice #${cycle.received_rank}).</p>`
      : html`<h2 class="section-title">You confirmed the swap</h2>
        <p class="muted mt-1 break-words">Waiting for ${plural(waiting, "more teacher")} to confirm. Your ${myCourse(cycle.gives)} lecture would move from ${cycle.gives.label} to ${cycle.receives.label} (your choice #${cycle.received_rank}).</p>`;
    const actions = pending
      ? html`
      <div class="flex flex-col gap-3 pt-1">
        <div class="flex flex-col sm:flex-row gap-2 sm:gap-3">
          <button class="btn-primary w-full sm:w-auto" id="btn-accept" type="button">${icon("check", 18)}Confirm swap</button>
          <button class="btn-danger w-full sm:w-auto" id="btn-decline" type="button">Decline</button>
        </div>
        <p class="text-xs faint">If anyone declines, the swap is cancelled for everyone. Whoever declines has their request closed; the others go back into the pool.</p>
      </div>`
      : "";
    return html`
    <div class="card card-pad border-brass/40 flex flex-col gap-5">
      <div class="flex flex-wrap items-center gap-2"><span class="chip-warn">${icon("schedule", 14)}${pending ? "Your answer needed" : "Waiting for others"}</span><span class="chip-neutral">${size}</span>${raw(tracking)}</div>
      <div>${raw(intro)}</div>
      ${raw(moveRow(cycle, "Now", "After the swap"))}
      ${raw(deadlineRow(cycle))}
      ${raw(membersList(cycle))}
      ${raw(actions)}
    </div>`;
  }

  return html`
  <div class="notice-bad">${icon("block", 20, "text-bad shrink-0")}
    <div><p class="font-semibold text-ink">This slot swap was cancelled</p><p class="mt-0.5">Check the activity below to see why.</p></div>
  </div>`;
}

function requestCard(request) {
  const prefs = request.preferences.map((p) => html`
    <li class="flex items-start gap-3 py-2.5 first:pt-0 last:pb-0">
      <span class="w-6 h-6 rounded-md bg-raised text-ink text-xs font-bold flex items-center justify-center shrink-0">${p.rank}</span>
      <div class="min-w-0">
        <p class="text-sm font-semibold text-ink break-words">${p.slot.label}</p>
        <p class="text-xs faint break-words">${p.slot.course_code} · ${p.slot.owner.name}</p>
      </div>
    </li>`).join("");
  const canWithdraw = request.status === "open";
  return html`
  <div class="card card-pad flex flex-col gap-5">
    <div class="flex flex-wrap items-center gap-2"><span class="chip-info">${icon("hourglass_empty", 14)}In the pool</span><span class="font-mono text-xs faint">${request.tracking_id}</span></div>
    <div>
      <h2 class="section-title">Your request is in the pool</h2>
      <p class="muted mt-1">Sent ${formatDateTime(request.created_at)}. Staff run slot rounds; when a chain of teachers who can all swap is found, it shows here and you get an email.</p>
    </div>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 items-start">
      <div class="rounded-lg border border-line bg-sunken p-3.5 min-w-0">
        <p class="text-xs faint">You offer</p>
        <p class="font-semibold text-ink mt-1 break-words">${myCourse(request.offered)}</p>
        <p class="text-sm muted break-words">${request.offered.label}</p>
      </div>
      <div class="rounded-lg border border-line bg-sunken p-3.5 min-w-0">
        <p class="text-xs faint mb-2.5">Slots you would prefer, best first</p>
        <ol>${raw(prefs)}</ol>
      </div>
    </div>
    ${canWithdraw ? raw(html`<div><button class="btn-secondary" id="btn-withdraw" type="button">${icon("undo", 18)}Withdraw request</button></div>`) : ""}
  </div>`;
}

function renderStatus() {
  const { request, cycle } = data;
  if (cycle) statusEl.innerHTML = cycleCard(cycle, request);
  else if (request && request.status !== "completed") statusEl.innerHTML = requestCard(request);
  else statusEl.innerHTML = "";
  statusEl.hidden = !statusEl.innerHTML;

  clearInterval(clockTimer);
  if (cycle?.status === "proposed") {
    clockTimer = setInterval(() => {
      const el = $("#countdown");
      if (el) el.textContent = deadlineText(cycle.deadline);
      if (countdown(cycle.deadline).done) { clearInterval(clockTimer); load(); }
    }, 30000);
  }
}

// ---------------------------------------------------------------- request builder
// Why a slot cannot be ranked right now, or "" if it can.
function blockedReason(slot) {
  if (slot.is_mine) return slot.id === offeredId ? "This is the lecture you are offering." : "You already teach this slot.";
  const clashId = slot.clashes_with.find((id) => id !== offeredId);
  if (clashId !== undefined) {
    const mine = data.my_slots.find((s) => s.id === clashId);
    return mine ? `Clashes with your ${mine.course_code} lecture (${mine.time_label}).` : "Clashes with another of your lectures.";
  }
  return "";
}

function stepHead(number, title, done, current, hint) {
  const badge = done
    ? `<span class="w-7 h-7 rounded-full bg-ok/10 text-ok border border-ok/30 flex items-center justify-center shrink-0"><span class="material-symbols-outlined text-[16px]" aria-hidden="true">check</span><span class="sr-only">Step ${number} done</span></span>`
    : `<span class="w-7 h-7 rounded-full ${current ? "bg-brass text-brass-ink" : "bg-raised text-ink-2 border border-line"} text-xs font-bold flex items-center justify-center shrink-0"><span class="sr-only">Step </span>${number}</span>`;
  return html`
  <div class="flex items-start gap-3">
    ${raw(badge)}
    <div class="min-w-0 pt-0.5">
      <h3 class="section-title">${title}</h3>
      ${hint ? raw(html`<p class="text-sm muted mt-0.5">${hint}</p>`) : ""}
    </div>
  </div>`;
}

function offerCards() {
  return data.my_slots.map((s) => html`
  <label class="relative block cursor-pointer min-w-0">
    <input class="peer sr-only" data-key="offer-${s.id}" name="offered" type="radio" value="${s.id}" ${offeredId === s.id ? "checked" : ""}/>
    <div class="h-full rounded-xl border border-line bg-panel p-4 transition-colors hover:border-line-strong peer-checked:border-brass peer-checked:bg-brass/5 peer-focus-visible:ring-2 peer-focus-visible:ring-brass/70 peer-focus-visible:ring-offset-2 peer-focus-visible:ring-offset-canvas">
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0">
          <p class="font-semibold text-ink break-words">${s.course_code}</p>
          <p class="text-sm muted break-words">${s.course_name}</p>
        </div>
        <span class="w-5 h-5 rounded-full border-2 ${raw(offeredId === s.id ? "border-brass bg-brass" : "border-line-strong")} flex items-center justify-center shrink-0 mt-0.5" aria-hidden="true">${offeredId === s.id ? raw('<span class="w-2 h-2 rounded-full bg-brass-ink"></span>') : ""}</span>
      </div>
      <p class="text-sm text-ink mt-3">${s.time_label}</p>
      <p class="text-xs faint">Hall ${s.hall}</p>
    </div>
  </label>`).join("");
}

// One slot as a button. `where` is "g" (week grid) or "l" (phone list) so each copy keeps its own focus key.
function slotButton(slot, where) {
  const reason = blockedReason(slot);
  const rank = ranked.indexOf(slot.id) + 1;
  const isOffer = slot.id === offeredId;
  let tone = "border-line bg-raised/40 hover:border-line-strong";
  if (rank) tone = "border-brass bg-brass/10";
  else if (isOffer) tone = "border-dashed border-line-strong bg-sunken";
  else if (reason) tone = "border-line bg-sunken opacity-60 cursor-not-allowed";
  const note = reason
    ? html`<span class="text-xs ${raw(slot.is_mine ? "text-ink-2" : "text-bad")}">${slot.is_mine ? (isOffer ? "You offer this" : "Your lecture") : "Clashes"}</span>`
    : slot.open_to_swap ? html`<span class="chip-info">Open to swap</span>` : "";
  const rankBadge = rank ? html`<span class="w-5 h-5 rounded-md bg-brass text-brass-ink text-xs font-bold flex items-center justify-center shrink-0" aria-hidden="true">${rank}</span>` : "";
  const sr = reason ? `Not available: ${reason}` : rank ? `Your choice ${rank}. Click to remove.` : slot.open_to_swap ? "Someone has offered this slot, so a swap is more likely." : "";
  const common = html`data-slot="${slot.id}" data-key="slot-${slot.id}-${where}" type="button" title="${reason || (rank ? `Your choice #${rank}. Click to remove it.` : `Add ${slot.course_code} to your list`)}" ${reason ? raw('aria-disabled="true"') : raw(`aria-pressed="${rank ? "true" : "false"}"`)}`;

  if (where === "g") {
    return html`
    <button class="w-full min-w-0 text-left rounded-lg border ${raw(tone)} p-2 flex flex-col gap-0.5 transition-colors" ${raw(common)}>
      <span class="flex items-center justify-between gap-1.5 min-w-0"><span class="text-sm font-semibold text-ink truncate">${slot.course_code}</span>${raw(rankBadge)}</span>
      <span class="text-xs text-ink-2">${slotTime(slot)}</span>
      <span class="text-xs text-ink-2">${slot.hall}</span>
      <span class="text-xs faint truncate" title="${slot.owner.name}">${slot.owner.name}</span>
      ${note ? raw(`<span class="mt-1">${note}</span>`) : ""}
      ${sr ? raw(html`<span class="sr-only">${sr}</span>`) : ""}
    </button>`;
  }
  return html`
  <button class="w-full min-w-0 text-left rounded-lg border ${raw(tone)} px-3 py-2.5 flex items-center gap-3 transition-colors" ${raw(common)}>
    <span class="text-xs text-ink-2 w-[86px] shrink-0">${slotTime(slot)}</span>
    <span class="min-w-0 flex-1">
      <span class="block text-sm font-semibold text-ink truncate">${slot.course_code} <span class="font-normal text-ink-2">${slot.course_name}</span></span>
      <span class="block text-xs faint truncate" title="${slot.owner.name}">${slot.hall} · ${slot.owner.name}</span>
      ${note ? raw(`<span class="block mt-1">${note}</span>`) : ""}
    </span>
    ${raw(rankBadge)}
    ${sr ? raw(html`<span class="sr-only">${sr}</span>`) : ""}
  </button>`;
}

function weekGrid() {
  const times = [...new Set(data.slots.map((s) => s.start_min))].sort((a, b) => a - b);
  const head = DAYS.map((d, i) => `<div class="px-1 pb-2 text-xs font-semibold text-ink-2" role="columnheader"><span aria-hidden="true">${d}</span><span class="sr-only">${DAY_NAMES[i]}</span></div>`).join("");
  const rows = times.map((t) => {
    const cells = DAYS.map((_, day) => {
      const here = data.slots.filter((s) => s.day === day && s.start_min === t);
      return `<div class="border-t border-line p-1 flex flex-col gap-1.5 min-w-0" role="cell">${here.map((s) => slotButton(s, "g")).join("")}</div>`;
    }).join("");
    return `<div class="contents" role="row"><div class="border-t border-line pt-2 pr-2 text-xs faint" role="rowheader">${hhmm(t)}</div>${cells}</div>`;
  }).join("");
  return `
  <div class="hidden sm:block overflow-x-auto">
    <div class="min-w-[720px] grid grid-cols-[3.5rem_repeat(6,minmax(0,1fr))]" role="table" aria-label="Weekly timetable">
      <div class="contents" role="row"><div role="columnheader"><span class="sr-only">Start time</span></div>${head}</div>
      ${rows}
    </div>
  </div>`;
}

function dayList() {
  const groups = DAYS.map((_, day) => {
    const here = data.slots.filter((s) => s.day === day);
    if (!here.length) return "";
    return html`
    <div>
      <h4 class="text-sm font-semibold text-ink mb-2">${DAY_NAMES[day]}</h4>
      <ul class="flex flex-col gap-1.5">${raw(here.map((s) => `<li>${slotButton(s, "l")}</li>`).join(""))}</ul>
    </div>`;
  }).join("");
  return `<div class="sm:hidden flex flex-col gap-5">${groups}</div>`;
}

function rankedPanel() {
  const items = ranked.map((id, i) => {
    const s = slotById(id);
    return html`
    <li class="flex items-center gap-2.5 py-2.5 first:pt-0 last:pb-0">
      <span class="w-6 h-6 rounded-md ${raw(i === 0 ? "bg-brass text-brass-ink" : "bg-raised text-ink")} text-xs font-bold flex items-center justify-center shrink-0">${i + 1}</span>
      <div class="min-w-0 flex-1">
        <p class="text-sm font-semibold text-ink break-words">${s.time_label} · ${s.hall}</p>
        <p class="text-xs faint truncate" title="${s.course_code} ${s.course_name} · ${s.owner.name}">${s.course_code} · ${s.owner.name}</p>
      </div>
      <div class="flex items-center shrink-0">
        <button class="icon-btn w-8 h-8 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent" data-move="up" data-id="${id}" data-key="up-${id}" type="button" aria-label="Move ${s.time_label} up" title="Move up" ${i === 0 ? "disabled" : ""}>${icon("arrow_upward", 18)}</button>
        <button class="icon-btn w-8 h-8 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent" data-move="down" data-id="${id}" data-key="down-${id}" type="button" aria-label="Move ${s.time_label} down" title="Move down" ${i === ranked.length - 1 ? "disabled" : ""}>${icon("arrow_downward", 18)}</button>
        <button class="icon-btn w-8 h-8 hover:text-bad" data-move="remove" data-id="${id}" data-key="rm-${id}" type="button" aria-label="Remove ${s.time_label}" title="Remove">${icon("close", 18)}</button>
      </div>
    </li>`;
  }).join("");
  const body = ranked.length
    ? `<ol class="divide-y divide-line/70">${items}</ol>`
    : `<div class="rounded-lg border border-dashed border-line-strong p-4 text-sm muted">No slots ranked yet. ${offeredId === null ? "Choose the lecture to move first, then click" : "Click"} slots in the timetable to add them, best first.</div>`;
  const ready = offeredId !== null && ranked.length > 0;
  return html`
  <div class="card card-pad flex flex-col gap-4 max-w-2xl">
    <div class="flex items-baseline justify-between gap-3">
      <h3 class="section-title outline-none" id="ranked-title" tabindex="-1">Your ranked list</h3>
      <span class="text-xs faint">${ranked.length} of ${MAX_CHOICES}</span>
    </div>
    ${raw(body)}
    <div aria-live="polite">${sendError ? raw(html`<div class="notice-bad">${icon("error", 18, "text-bad shrink-0 mt-px")}<p class="break-words">${sendError}</p></div>`) : ""}</div>
    <button class="btn-primary w-full sm:w-auto sm:self-start" id="btn-send" type="button" ${ready ? "" : "disabled"}>${icon("send", 18)}Send request</button>
    <p class="text-xs faint">${ready ? "You can withdraw it any time before a swap is found." : offeredId === null ? "Choose a lecture in step 1 and rank at least one slot to send." : "Rank at least one slot to send."}</p>
  </div>`;
}

function renderBuilder() {
  const { request } = data;
  const active = request && request.status !== "completed";
  builderEl.hidden = !!active;
  if (active) { builderEl.innerHTML = ""; return; }

  const focusKey = document.activeElement?.dataset?.key;

  if (!data.my_slots.length) {
    builderEl.innerHTML = html`
    <div class="card card-pad flex flex-col gap-2">
      <h2 class="section-title">Ask to move a lecture</h2>
      <p class="muted">You have no lectures in the timetable, so there is nothing to offer yet. If this looks wrong, ask the academic staff to check the timetable.</p>
    </div>`;
    return;
  }

  const others = data.slots.filter((s) => !s.is_mine);
  const step2Body = others.length
    ? html`
      <div class="flex flex-col gap-4">
        <div class="card p-3 sm:p-4 min-w-0">
          ${raw(weekGrid())}
          ${raw(dayList())}
          <p class="text-xs faint mt-4 flex items-start gap-1.5">${icon("info", 16, "shrink-0")}<span>Slots marked “Open to swap” are already offered by another teacher, so a swap is more likely. Greyed-out slots are yours or clash with your other lectures.</span></p>
        </div>
        ${raw(rankedPanel())}
      </div>`
    : `<div class="card card-pad muted">There are no other lecture slots in the timetable yet, so there is nothing to rank.</div>`;

  builderEl.innerHTML = html`
  <div class="flex flex-col gap-6">
    <div>
      <h2 class="section-title">Ask to move a lecture</h2>
      <p class="text-sm muted mt-0.5">Two steps, then send. Nothing changes until everyone in a swap confirms and staff approve.</p>
    </div>
    <div class="flex flex-col gap-4">
      ${raw(stepHead(1, "Choose the lecture you want to move", offeredId !== null, offeredId === null, "You give up this slot; the course goes with you."))}
      <fieldset class="sm:pl-10">
        <legend class="sr-only">Lecture you want to move</legend>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">${raw(offerCards())}</div>
      </fieldset>
    </div>
    <div class="flex flex-col gap-4">
      ${raw(stepHead(2, `Rank up to ${MAX_CHOICES} slots you would prefer`, false, offeredId !== null, "Click a slot to add it. Your first choice is the one you want most."))}
      <div class="sm:pl-10">${raw(step2Body)}</div>
    </div>
  </div>`;

  if (focusKey) builderEl.querySelector(`[data-key="${focusKey}"]`)?.focus();
}

function chooseOffer(id) {
  offeredId = id;
  sendError = "";
  const before = ranked.length;
  ranked = ranked.filter((sid) => !blockedReason(slotById(sid)));
  renderBuilder();
  if (ranked.length < before) {
    toast("Some slots were removed", "They clash with a lecture you are keeping.", { icon: "info" });
  }
}

function toggleSlot(id) {
  const slot = slotById(id);
  if (offeredId === null) {
    toast("Choose a lecture first", "Pick the lecture you want to move in step 1.", { icon: "info" });
    builderEl.querySelector('input[name="offered"]')?.focus();
    return;
  }
  const reason = blockedReason(slot);
  if (reason) { toast("You can't pick this slot", reason, { icon: "block", tone: "error" }); return; }
  sendError = "";
  if (ranked.includes(id)) ranked = ranked.filter((x) => x !== id);
  else if (ranked.length >= MAX_CHOICES) {
    toast(`You can rank at most ${MAX_CHOICES} slots`, "Remove one from your list to add another.", { icon: "info" });
    return;
  } else ranked = [...ranked, id];
  renderBuilder();
}

function moveRanked(id, how) {
  const i = ranked.indexOf(id);
  const next = [...ranked];
  if (how === "remove") next.splice(i, 1);
  else {
    const j = how === "up" ? i - 1 : i + 1;
    if (j < 0 || j >= next.length) return;
    [next[i], next[j]] = [next[j], next[i]];
  }
  ranked = next;
  sendError = "";
  renderBuilder();
  if (how === "remove") {
    const neighbour = ranked[Math.min(i, ranked.length - 1)];
    (neighbour !== undefined ? $(`[data-key="rm-${neighbour}"]`) : $("#ranked-title"))?.focus();
  } else {
    const key = `${how}-${id}`;
    const el = $(`[data-key="${key}"]`);
    (el && !el.disabled ? el : $(`[data-key="rm-${id}"]`))?.focus();
  }
}

async function sendRequest(button) {
  const restore = setBusy(button, "Sending…");
  try {
    const result = await api("/api/faculty/requests", { method: "POST", body: { slot_id: offeredId, wanted: ranked } });
    toast("Request sent", `Tracking ID ${result.tracking_id}. You are in the pool for the next slot round.`, { icon: "send" });
    offeredId = null;
    ranked = [];
    sendError = "";
    await load();
    statusEl.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    restore();
    sendError = error.message;
    if (error.code === "already_active") await load();
    else renderBuilder();
  }
}

builderEl.addEventListener("change", (e) => {
  if (e.target.name === "offered") chooseOffer(Number(e.target.value));
});
builderEl.addEventListener("click", (e) => {
  const slotBtn = e.target.closest("[data-slot]");
  if (slotBtn) return toggleSlot(Number(slotBtn.dataset.slot));
  const moveBtn = e.target.closest("[data-move]");
  if (moveBtn && !moveBtn.disabled) return moveRanked(Number(moveBtn.dataset.id), moveBtn.dataset.move);
  const send = e.target.closest("#btn-send");
  if (send && !send.disabled) sendRequest(send);
});

// ---------------------------------------------------------------- activity
function renderActivity() {
  const { events } = data;
  const list = events.length
    ? `<ul class="divide-y divide-line/70">${events.map((e) => html`
      <li class="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-0.5 sm:gap-4 py-3 first:pt-0 last:pb-0">
        <p class="text-sm text-ink-2 break-words min-w-0">${e.message}</p>
        <time class="text-xs faint whitespace-nowrap shrink-0" datetime="${e.created_at}" title="${formatDateTime(e.created_at)}">${timeAgo(e.created_at)}</time>
      </li>`).join("")}</ul>`
    : `<p class="text-sm muted">Nothing yet. When you send a request or a swap is found for you, it shows here.</p>`;
  activityEl.innerHTML = `<div class="card card-pad"><h2 class="section-title mb-4">Activity</h2>${list}</div>`;
}

// ---------------------------------------------------------------- load
function render() {
  const run = data.last_run;
  $("#run-line").textContent = run ? `Last slot round: ${timeAgo(run.created_at)}.` : "No slot round has run yet.";
  // Keep the builder choices only while they still make sense for the fresh data.
  if (!data.my_slots.some((s) => s.id === offeredId)) offeredId = data.my_slots.length === 1 ? data.my_slots[0].id : null;
  ranked = ranked.filter((id) => slotById(id) && !blockedReason(slotById(id)));
  renderStatus();
  renderBuilder();
  renderActivity();
}

async function act(button, label, path, method, success) {
  const restore = setBusy(button, label);
  try {
    const result = await api(path, { method });
    toast(...success(result));
  } catch (error) {
    restore();
    toastError(error);
  }
  await load();
}

statusEl.addEventListener("click", (e) => {
  const button = e.target.closest("button");
  if (!button || button.disabled) return;
  const cycle = data.cycle;
  if (button.id === "btn-accept") {
    act(button, "Confirming…", `/api/faculty/cycles/${cycle.id}/accept`, "POST", (r) => (r.status === "confirmed"
      ? ["Everyone has confirmed", "Staff approve the swap next.", { icon: "task_alt" }]
      : ["Swap confirmed", "Waiting for the other teachers to confirm.", { icon: "check_circle" }]));
  } else if (button.id === "btn-decline") {
    if (!confirm("Decline this slot swap? It will be cancelled for everyone in it, and your request will close.")) return;
    act(button, "Declining…", `/api/faculty/cycles/${cycle.id}/decline`, "POST",
      () => ["Swap declined", "The swap was cancelled and your request is closed.", { icon: "block", tone: "error" }]);
  } else if (button.id === "btn-withdraw") {
    if (!confirm("Withdraw your request? You can send a new one later.")) return;
    act(button, "Withdrawing…", "/api/faculty/requests/current", "DELETE",
      () => ["Request withdrawn", "You are no longer in the pool.", { icon: "undo" }]);
  } else if (button.id === "btn-retry") {
    showLoading();
    load();
  }
});

function showLoading() {
  statusEl.hidden = false;
  builderEl.hidden = false;
  activityEl.hidden = false;
  statusEl.innerHTML = `<div class="skeleton h-44 w-full"></div>`;
  builderEl.innerHTML = `<div class="flex flex-col gap-4"><div class="skeleton h-6 w-56"></div><div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3"><div class="skeleton h-24"></div><div class="skeleton h-24"></div></div><div class="skeleton h-80 w-full"></div></div>`;
  activityEl.innerHTML = `<div class="skeleton h-40 w-full"></div>`;
}

async function load() {
  try {
    data = await api("/api/faculty/home");
    render();
  } catch (error) {
    if (error.status === 401) return location.replace("/");
    clearInterval(clockTimer);
    statusEl.hidden = false;
    builderEl.hidden = true;
    activityEl.hidden = true;
    statusEl.innerHTML = html`
    <div class="notice-bad items-start">
      ${icon("error", 20, "text-bad shrink-0")}
      <div class="min-w-0">
        <p class="font-semibold text-ink">Couldn't load your lecture slots</p>
        <p class="mt-0.5 break-words">${error.message}</p>
        <button class="btn-secondary btn-sm mt-3" id="btn-retry" type="button">Try again</button>
      </div>
    </div>`;
  }
}

const me = await requireUser("faculty");
fillHeader(me);
load();
