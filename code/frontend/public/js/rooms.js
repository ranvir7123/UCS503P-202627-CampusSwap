// Find rooms: filter rooms, build a ranked list of up to 5 choices (exact rooms
// or room types), and send it as a swap request.
import { api, requireUser } from "./api.js";
import { fillHeader } from "./nav.js";
import { $, $$, formatDateTime, html, plural, raw, setBusy, toast } from "./ui.js";

const MAX = 5;
const PAGE_SIZE = { grid: 6, compact: 12 };
const NO_FILTERS = { hostel: "", floor: "", seater: "", ac: false, attached: false, open: false, search: "" };

const TOGGLE_ON = "btn-secondary btn-sm border-brass/50 bg-brass/10 text-brass hover:border-brass";
const TOGGLE_OFF = "btn-secondary btn-sm";
const VIEW_ON = "h-8 px-2.5 rounded-md text-xs font-semibold flex items-center gap-1 bg-raised text-ink";
const VIEW_OFF = "h-8 px-2.5 rounded-md text-xs font-semibold flex items-center gap-1 text-ink-2 hover:text-ink";
const PANEL_OPEN = ["flex", "fixed", "inset-0", "z-50", "overflow-y-auto", "bg-canvas", "p-4", "pb-8"];

// state.queue holds entries: { kind: "room", room } or { kind: "type", type: { hostel, seater, ac, floor } }
const state = {
  rooms: [], hostels: [], lastRun: null, request: null, loaded: false,
  queue: [], filters: { ...NO_FILTERS },
  sort: "open", view: "grid", page: 1,
};
let me;
const wide = window.matchMedia("(min-width: 1024px)");
const draftKey = () => `campusswap-draft-${me.id}`;
const locked = () => state.request && ["open", "matched"].includes(state.request.status);
const bedsLabel = (n) => (n === 1 ? "Single" : n === 2 ? "Double sharing" : "Triple sharing");
const floorLabel = (f) => (f === 0 ? "Ground floor" : `Floor ${f}`);
const shortName = (room) => `${room.hostel.name} · ${room.number}`;
const hostelName = (code) => state.hostels.find((h) => h.code === code)?.name || `Hostel ${code}`;
const toastWhere = () => (wide.matches ? "bottom" : "top");

// ---------------------------------------------------------------- room types
// Same wording as Preference.label on the server, so this page and My swap agree.
function typeLabel(t) {
  const seater = t.seater ? `${t.seater}-seater ` : "";
  const ac = t.ac === true ? "AC " : t.ac === false ? "non-AC " : "";
  const floor = t.floor !== null && t.floor !== undefined ? `, floor ${t.floor}` : "";
  return `Any ${seater}${ac}room in ${hostelName(t.hostel)}${floor}`;
}
const typeKey = (t) => [t.hostel, t.seater ?? "", t.ac ?? "", t.floor ?? ""].join("|");
const fitsType = (t, r) => r.hostel.code === t.hostel
  && (t.seater === null || r.seater === t.seater)
  && (t.ac === null || r.ac === t.ac)
  && (t.floor === null || r.floor === t.floor);
// Rooms (other than your own) that a type stands for. The server refuses a type with none.
function typeMatches(t) {
  const fits = state.rooms.filter((r) => fitsType(t, r));
  return { count: fits.filter((r) => !r.is_own).length, includesOwn: fits.some((r) => r.is_own) };
}
function matchText({ count, includesOwn }) {
  if (!count) return "Matches no rooms right now";
  return `Matches ${plural(count, "room")}${includesOwn ? " besides yours" : ""}`;
}
const floorsOf = (code) => [...new Set(state.rooms.filter((r) => !code || r.hostel.code === code).map((r) => r.floor))].sort((a, b) => a - b);

function readTypeForm() {
  const seater = $("#type-seater").value;
  const ac = $("#type-ac").value;
  const floor = $("#type-floor").value;
  return {
    hostel: $("#type-hostel").value,
    seater: seater ? Number(seater) : null,
    ac: ac === "" ? null : ac === "true",
    floor: floor === "" ? null : Number(floor),
  };
}

function fillTypeFloors() {
  const select = $("#type-floor");
  const before = select.value;
  const floors = floorsOf($("#type-hostel").value);
  select.innerHTML = `<option value="">Any</option>`
    + floors.map((f) => html`<option value="${f}">${f === 0 ? "Ground" : f}</option>`).join("");
  select.value = floors.includes(Number(before)) && before !== "" ? before : "";
}

// Why the current type can't be added, or "" when it can.
function typeProblem(t) {
  const dupe = state.queue.findIndex((e) => e.kind === "type" && typeKey(e.type) === typeKey(t));
  if (dupe >= 0) return `This room type is already choice ${dupe + 1} in your list.`;
  if (state.queue.length >= MAX) return `You already have ${MAX} choices. Remove one to add this room type.`;
  if (!typeMatches(t).count) return "No room other than yours fits this type, so it can't be sent. Change the beds, AC or floor.";
  return "";
}

function renderTypePreview() {
  if (!state.hostels.length) return;
  const t = readTypeForm();
  const m = typeMatches(t);
  const problem = typeProblem(t);
  $("#type-preview").innerHTML = html`
    <span class="text-sm font-semibold text-ink break-words">${typeLabel(t)}</span>
    <span class="text-xs ${raw(m.count ? "muted" : "text-bad")} flex items-center gap-1">
      <span class="material-symbols-outlined text-[16px]" aria-hidden="true">${m.count ? "meeting_room" : "warning"}</span>${matchText(m)}
    </span>
    ${problem ? raw(html`<span class="text-xs ${raw(m.count ? "text-brass" : "muted")}">${problem}</span>`) : ""}`;
  $("#type-add").disabled = Boolean(problem);
}

function setTypeFormOpen(open) {
  $("#type-form").hidden = !open;
  $("#type-toggle").setAttribute("aria-expanded", String(open));
  $("#type-toggle-icon").textContent = open ? "expand_less" : "expand_more";
  if (open) renderTypePreview();
}

function addType() {
  const t = readTypeForm();
  if (typeProblem(t)) return renderTypePreview();
  state.queue.push({ kind: "type", type: t });
  saveDraft();
  update();
  toast(`Added a room type as choice ${state.queue.length}`, typeLabel(t), { icon: "playlist_add", position: toastWhere() });
}

// ---------------------------------------------------------------- filtering
function filtered() {
  const f = state.filters;
  const q = f.search.trim().toLowerCase();
  const list = state.rooms.filter((r) =>
    (!f.hostel || r.hostel.code === f.hostel)
    && (f.floor === "" || String(r.floor) === f.floor)
    && (!f.seater || String(r.seater) === f.seater)
    && (!f.ac || r.ac)
    && (!f.attached || r.washroom === "attached")
    && (!f.open || r.open_to_swap > 0)
    && (!q || `${r.hostel.name} ${r.hostel.code} block ${r.block} ${r.number} ${r.tags.join(" ")}`.toLowerCase().includes(q)));
  const byNumber = (a, b) => a.hostel.code.localeCompare(b.hostel.code) || a.number.localeCompare(b.number);
  const sorters = {
    open: (a, b) => b.open_to_swap - a.open_to_swap || byNumber(a, b),
    hostel: byNumber,
    floor: (a, b) => a.floor - b.floor || byNumber(a, b),
  };
  return list.sort(sorters[state.sort]);
}

function activeChipList() {
  const f = state.filters;
  const chips = [];
  if (f.hostel) chips.push(["hostel", hostelName(f.hostel)]);
  if (f.floor !== "") chips.push(["floor", floorLabel(Number(f.floor))]);
  if (f.seater) chips.push(["seater", bedsLabel(Number(f.seater))]);
  if (f.ac) chips.push(["ac", "AC only"]);
  if (f.attached) chips.push(["attached", "Attached washroom"]);
  if (f.open) chips.push(["open", "Someone wants to swap"]);
  if (f.search.trim()) chips.push(["search", `“${f.search.trim()}”`]);
  return chips;
}

function activeChips() {
  const chips = activeChipList();
  const strip = $("#active-filter-strip");
  const panelChips = chips.filter(([key]) => key !== "search").length;
  $("#filters-toggle-label").textContent = panelChips ? `Filters (${panelChips})` : "Filters";
  if (!chips.length) {
    strip.innerHTML = `<span class="faint">No filters. Showing every room in the hostels you can live in.</span>`;
    return;
  }
  strip.innerHTML = chips.map(([key, label]) => html`<span class="chip-neutral max-w-full pr-1"><span class="truncate">${label}</span><button aria-label="Remove filter: ${label}" class="inline-flex items-center justify-center w-5 h-5 rounded hover:bg-line hover:text-ink" data-clear="${key}" type="button"><span class="material-symbols-outlined text-[14px]" aria-hidden="true">close</span></button></span>`).join("")
    + `<button class="btn-ghost btn-sm h-6 px-2" data-clear="all" type="button">Clear all</button>`;
}

function clearFilter(key) {
  if (key === "all") state.filters = { ...NO_FILTERS };
  else state.filters[key] = typeof state.filters[key] === "boolean" ? false : "";
  state.page = 1;
  syncControls();
  update();
}

function syncControls() {
  const f = state.filters;
  $("#filter-hostel").value = f.hostel;
  $("#filter-floor").value = f.floor;
  $("#filter-seater").value = f.seater;
  $("#search").value = f.search;
  for (const b of $$("[data-toggle]")) {
    const on = f[b.dataset.toggle];
    b.className = on ? TOGGLE_ON : TOGGLE_OFF;
    b.setAttribute("aria-pressed", String(on));
  }
}

// ---------------------------------------------------------------- room cards
function actionButton(room) {
  const rank = state.queue.findIndex((e) => e.kind === "room" && e.room.id === room.id);
  if (room.is_own) return `<button class="btn-secondary btn-sm" disabled type="button"><span class="material-symbols-outlined text-[16px]" aria-hidden="true">home</span>Your room</button>`;
  if (locked()) return `<button class="btn-secondary btn-sm" disabled type="button"><span class="material-symbols-outlined text-[16px]" aria-hidden="true">lock</span>Request already sent</button>`;
  if (rank >= 0) return html`<button aria-label="Remove ${shortName(room)} from your choices (choice ${rank + 1})" class="btn-secondary btn-sm border-brass/40 text-brass" data-unrank="${room.id}" type="button"><span class="material-symbols-outlined text-[16px]" aria-hidden="true">check</span>Choice ${rank + 1} · Remove</button>`;
  if (state.queue.length >= MAX) return html`<button class="btn-secondary btn-sm" disabled title="You already have ${MAX} choices" type="button">${MAX} of ${MAX} chosen</button>`;
  return html`<button aria-label="Add ${shortName(room)} to your choices" class="btn-secondary btn-sm" data-rank="${room.id}" type="button"><span class="material-symbols-outlined text-[16px] text-brass" aria-hidden="true">add</span>Add to choices</button>`;
}

function statusChip(room) {
  if (room.is_own) return `<span class="chip-neutral"><span class="material-symbols-outlined text-[14px]" aria-hidden="true">home</span>Your room</span>`;
  if (room.open_to_swap > 0) return html`<span class="chip-info"><span class="material-symbols-outlined text-[14px]" aria-hidden="true">swap_horiz</span>${room.open_to_swap} open to swap</span>`;
  return "";
}

function gridCard(room) {
  const swapLine = room.is_own ? "You live here"
    : room.open_to_swap ? `${room.open_to_swap} of ${room.seater} ${room.seater > 1 ? "people" : "person"} here want${room.open_to_swap === 1 ? "s" : ""} to swap`
      : "No one here has asked to swap yet";
  return html`
  <article class="card p-4 sm:p-5 flex flex-col gap-3 ${raw(room.is_own ? "border-line-strong" : "")}">
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <p class="text-xs muted break-words">${room.hostel.name} · Block ${room.block} · ${floorLabel(room.floor)}</p>
        <h3 class="section-title mt-0.5 break-words">Room <span class="font-mono">${room.number}</span></h3>
      </div>
      <div class="shrink-0">${raw(statusChip(room))}</div>
    </div>
    <div class="flex flex-wrap gap-1.5">
      <span class="chip-neutral"><span class="material-symbols-outlined text-[14px]" aria-hidden="true">bed</span>${bedsLabel(room.seater)}</span>
      <span class="chip-neutral"><span class="material-symbols-outlined text-[14px]" aria-hidden="true">${room.ac ? "ac_unit" : "mode_fan"}</span>${room.ac ? "AC" : "Non-AC"}</span>
      <span class="chip-neutral"><span class="material-symbols-outlined text-[14px]" aria-hidden="true">shower</span>${room.washroom === "attached" ? "Attached washroom" : "Common washroom"}</span>
    </div>
    ${room.tags.length ? raw(html`<p class="text-xs faint break-words">${room.tags.join(" · ")}</p>`) : ""}
    <div class="flex items-center justify-between gap-3 flex-wrap pt-3 border-t border-line">
      <span class="text-xs muted">${swapLine}</span>
      ${raw(actionButton(room))}
    </div>
  </article>`;
}

function compactRow(room) {
  return html`
  <div class="px-4 py-3 flex flex-col sm:flex-row sm:items-center gap-x-4 gap-y-2 ${raw(room.is_own ? "bg-raised/40" : "")}">
    <div class="flex-1 min-w-0">
      <span class="font-mono text-[13px] text-ink">${room.hostel.code}-${room.number}</span>
      <span class="block text-xs muted break-words">${room.hostel.name} · Block ${room.block} · ${floorLabel(room.floor)}</span>
      <span class="block text-xs faint break-words">${bedsLabel(room.seater)} · ${room.ac ? "AC" : "Non-AC"} · ${room.washroom === "attached" ? "Attached washroom" : "Common washroom"}</span>
    </div>
    <div class="flex items-center justify-between sm:justify-end gap-3 shrink-0">
      <span class="text-xs sm:w-24 ${raw(room.open_to_swap && !room.is_own ? "text-info" : "faint")}">${room.is_own ? "You live here" : room.open_to_swap ? `${room.open_to_swap} open to swap` : "No one swapping"}</span>
      ${raw(actionButton(room))}
    </div>
  </div>`;
}

function renderList() {
  const target = $("#room-list");
  target.setAttribute("aria-busy", "false");
  const list = filtered();
  const size = PAGE_SIZE[state.view];
  const pages = Math.max(1, Math.ceil(list.length / size));
  state.page = Math.min(state.page, pages);
  const slice = list.slice((state.page - 1) * size, state.page * size);
  const withOpen = state.rooms.filter((r) => r.open_to_swap > 0 && !r.is_own).length;
  $("#count-label").textContent = `${list.length} of ${plural(state.rooms.length, "room")} · ${withOpen} with someone open to swap`;

  if (!state.rooms.length) {
    target.innerHTML = `<div class="card card-pad flex flex-col items-start gap-2"><h3 class="section-title">No rooms to show</h3><p class="muted">There are no rooms yet in the hostels you can live in. Check back after the hostel office adds them.</p></div>`;
  } else if (!list.length) {
    target.innerHTML = `<div class="card card-pad flex flex-col items-start gap-2"><span class="material-symbols-outlined text-[24px] faint" aria-hidden="true">search_off</span><h3 class="section-title">No rooms match these filters</h3><p class="muted">Remove a filter or two to see more rooms.</p><button class="btn-secondary mt-2" data-clear="all" type="button">Clear filters</button></div>`;
  } else if (state.view === "grid") {
    target.innerHTML = slice.map(gridCard).join("");
  } else {
    target.innerHTML = `<div class="card overflow-hidden divide-y divide-line">${slice.map(compactRow).join("")}</div>`;
  }
  renderPagination(list.length, pages);
}

function renderPagination(total, pages) {
  const size = PAGE_SIZE[state.view];
  const from = total ? (state.page - 1) * size + 1 : 0;
  const to = Math.min(total, state.page * size);
  if (!total) { $("#pagination").innerHTML = ""; return; }
  const num = (n) => html`<button ${raw(n === state.page ? "aria-current=\"page\"" : "")} aria-label="Page ${n}" class="btn-ghost btn-sm w-8 px-0 ${raw(n === state.page ? "bg-raised text-ink" : "")}" data-page="${n}" type="button">${n}</button>`;
  $("#pagination").innerHTML = html`<span>Showing ${from}–${to} of ${total}</span>`
    + (pages > 1 ? html`<nav aria-label="Pages of rooms" class="flex items-center gap-1 flex-wrap">
        <button class="btn-ghost btn-sm" data-page="${state.page - 1}" ${raw(state.page === 1 ? "disabled" : "")} type="button" aria-label="Previous page"><span class="material-symbols-outlined text-[18px]" aria-hidden="true">chevron_left</span><span class="hidden sm:inline">Previous</span></button>
        ${raw(Array.from({ length: pages }, (_, i) => num(i + 1)).join(""))}
        <button class="btn-ghost btn-sm" data-page="${state.page + 1}" ${raw(state.page === pages ? "disabled" : "")} type="button" aria-label="Next page"><span class="hidden sm:inline">Next</span><span class="material-symbols-outlined text-[18px]" aria-hidden="true">chevron_right</span></button>
      </nav>` : "");
}

// ---------------------------------------------------------------- ranked list
// One entry as { title, titleHtml, sub, warn } for display.
function describe(entry) {
  if (entry.kind === "room") {
    const r = entry.room;
    return {
      name: shortName(r),
      titleHtml: html`${r.hostel.name} · <span class="font-mono text-[13px]">${r.number}</span>`,
      sub: `${bedsLabel(r.seater)} · ${r.ac ? "AC" : "Non-AC"} · ${floorLabel(r.floor)}`,
      warn: false,
    };
  }
  const m = typeMatches(entry.type);
  const label = entry.label || typeLabel(entry.type);
  return { name: label, titleHtml: html`${label}`, sub: `Room type · ${matchText(m)}`, warn: !m.count };
}

function queueItem(entry, i, count, isLocked) {
  const d = describe(entry);
  const rankClass = i === 0 ? "bg-brass/15 text-brass border-brass/30" : "bg-raised text-ink-2 border-line";
  const controls = isLocked ? "" : html`
    <div class="flex items-center shrink-0 -mr-1">
      <button aria-label="Move ${d.name} up" class="icon-btn w-8 h-8 disabled:opacity-30 disabled:pointer-events-none" data-move="${i}" data-dir="-1" ${raw(i === 0 ? "disabled" : "")} type="button"><span class="material-symbols-outlined text-[18px]" aria-hidden="true">arrow_upward</span></button>
      <button aria-label="Move ${d.name} down" class="icon-btn w-8 h-8 disabled:opacity-30 disabled:pointer-events-none" data-move="${i}" data-dir="1" ${raw(i === count - 1 ? "disabled" : "")} type="button"><span class="material-symbols-outlined text-[18px]" aria-hidden="true">arrow_downward</span></button>
      <button aria-label="Remove ${d.name}" class="icon-btn w-8 h-8 hover:text-bad" data-remove="${i}" type="button"><span class="material-symbols-outlined text-[18px]" aria-hidden="true">close</span></button>
    </div>`;
  return html`
  <li class="queue-item flex items-center gap-3 p-2.5 rounded-lg border border-line bg-sunken/60 ${raw(isLocked ? "" : "cursor-grab")}" data-index="${i}" ${raw(isLocked ? "" : "draggable=\"true\"")}>
    <span class="w-7 h-7 shrink-0 rounded-md border text-xs font-bold flex items-center justify-center ${raw(rankClass)}"><span class="sr-only">Choice </span>${i + 1}</span>
    <div class="flex flex-col min-w-0 flex-1">
      <span class="text-sm font-semibold text-ink break-words">${raw(d.titleHtml)}</span>
      <span class="text-xs ${raw(d.warn ? "text-bad" : "faint")} break-words">${d.sub}</span>
    </div>
    ${raw(controls)}
  </li>`;
}

function lockedEntries() {
  return state.request.preferences.map((p) => (p.kind === "type"
    ? { kind: "type", type: p.type, label: p.label }
    : { kind: "room", room: p.room }));
}

function renderLockedNotice() {
  const box = $("#locked-notice");
  if (!locked()) { box.hidden = true; box.innerHTML = ""; return; }
  const matched = state.request.status === "matched";
  box.hidden = false;
  box.innerHTML = html`
    <div class="${raw(matched ? "notice-warn" : "notice-info")}">
      <span class="material-symbols-outlined text-[18px] ${raw(matched ? "text-brass" : "text-info")} shrink-0" aria-hidden="true">${matched ? "hourglass_top" : "lock"}</span>
      <div class="flex flex-col gap-1 min-w-0">
        <span class="font-semibold text-ink">${matched ? "You're in a proposed swap" : "You already have a request in the pool"}</span>
        <span>${matched
          ? "Open My swap to confirm or decline it. You can't send a new list while it is waiting for answers."
          : raw(html`Request <span class="code">${state.request.tracking_id}</span> is waiting for the next matching round. To change your choices, withdraw it first, then send a new list.`)}</span>
      </div>
    </div>
    <a class="btn-primary w-full h-10" href="/dashboard.html">${matched ? "See my swap" : "Track it on My swap"}</a>`;
}

function renderQueue() {
  const isLocked = locked();
  const entries = isLocked ? lockedEntries() : state.queue;
  const count = entries.length;
  const items = entries.map((e, i) => queueItem(e, i, count, isLocked));
  if (!isLocked) {
    for (let n = count + 1; n <= MAX; n++) {
      const first = n === count + 1;
      items.push(html`<li><button class="w-full flex items-center gap-3 p-2.5 rounded-lg border border-dashed border-line text-left hover:border-line-strong hover:bg-raised/40 ${raw(first ? "" : "opacity-70")}" data-empty type="button"><span class="w-7 h-7 shrink-0 rounded-md border border-dashed border-line-strong text-xs font-bold faint flex items-center justify-center">${n}</span><span class="text-xs muted">${first ? (count ? "Add a backup choice" : "Add a room from the list, or a room type below") : "Optional backup choice"}</span></button></li>`);
    }
  }
  $("#ranked-queue-container").innerHTML = items.join("");
  $("#queue-counter-badge").textContent = isLocked ? `Sent · ${plural(count, "choice")}` : `${count} of ${MAX} chosen`;
  $("#phone-bar-text").textContent = isLocked ? `Request sent · ${state.request.tracking_id}` : `${count} of ${MAX} chosen`;
  $("#phone-bar-btn").textContent = isLocked ? "View" : "Review";
  renderLockedNotice();

  const submit = $("#lock-submit-btn");
  const secondary = $("#secondary-btn");
  $("#type-box").hidden = isLocked || !state.hostels.length;
  submit.hidden = isLocked;
  if (isLocked) {
    const matched = state.request.status === "matched";
    $("#queue-help").textContent = "These are the choices you sent, best first.";
    secondary.hidden = matched;
    secondary.disabled = false;
    secondary.className = "btn-danger w-full";
    secondary.innerHTML = `<span class="material-symbols-outlined text-[18px]" aria-hidden="true">undo</span>Withdraw request`;
    secondary.dataset.mode = "withdraw";
  } else {
    $("#queue-help").textContent = "Put your favourite first. Use the arrows (or drag) to change the order. The matching round tries your first choice first, then the next one that is still free.";
    const anyEmpty = state.queue.some((e) => e.kind === "type" && !typeMatches(e.type).count);
    submit.disabled = count === 0 || anyEmpty;
    submit.textContent = !count ? "Add at least one choice"
      : anyEmpty ? "Remove the room type that matches no rooms" : `Send request with ${plural(count, "choice")}`;
    secondary.hidden = false;
    secondary.disabled = count === 0;
    secondary.className = "btn-ghost w-full";
    secondary.textContent = "Clear list";
    secondary.dataset.mode = "clear";
  }
  renderTypePreview();
}

function renderYield() {
  const run = state.lastRun;
  if (run) {
    $("#yield-pill").textContent = `${run.yield_pct}% matched`;
    $("#yield-text").textContent = `${run.matched} of ${run.pool_size} students got a swap in the last round (${formatDateTime(run.created_at)}).`;
  } else {
    $("#yield-pill").textContent = "No rounds yet";
    $("#yield-text").textContent = "Hostel staff haven't run a matching round yet. Your request will be part of the next one.";
  }
}

// ---------------------------------------------------------------- draft (kept in this browser)
function saveDraft() {
  clearSubmitError();
  const data = state.queue.map((e) => (e.kind === "room" ? { room_id: e.room.id } : { type: e.type }));
  try { localStorage.setItem(draftKey(), JSON.stringify(data)); } catch { /* storage may be blocked */ }
}
function loadDraft() {
  let saved = [];
  try { saved = JSON.parse(localStorage.getItem(draftKey()) || "[]"); } catch { saved = []; }
  if (!Array.isArray(saved)) saved = [];
  const seen = new Set();
  const out = [];
  for (const item of saved) {
    const roomId = typeof item === "number" ? item : item?.room_id; // older drafts were plain room ids
    if (roomId !== undefined && roomId !== null) {
      const room = state.rooms.find((r) => r.id === roomId);
      if (room && !room.is_own && !seen.has(`r${room.id}`)) { seen.add(`r${room.id}`); out.push({ kind: "room", room }); }
    } else if (item?.type && state.hostels.some((h) => h.code === item.type.hostel)) {
      const t = { hostel: item.type.hostel, seater: item.type.seater ?? null, ac: item.type.ac ?? null, floor: item.type.floor ?? null };
      if (!seen.has(`t${typeKey(t)}`)) { seen.add(`t${typeKey(t)}`); out.push({ kind: "type", type: t }); }
    }
  }
  state.queue = out.slice(0, MAX);
}

function update() {
  activeChips();
  renderList();
  renderQueue();
}

// Put keyboard focus back on a sensible control after the list is redrawn.
function refocus(selectors) {
  for (const sel of selectors) {
    const el = document.querySelector(sel);
    if (el && !el.disabled) { el.focus(); return; }
  }
}

// ---------------------------------------------------------------- actions
function rank(id) {
  const room = state.rooms.find((r) => r.id === id);
  if (!room || room.is_own || state.queue.length >= MAX || state.queue.some((e) => e.kind === "room" && e.room.id === id)) return;
  state.queue.push({ kind: "room", room });
  saveDraft();
  update();
  refocus([`[data-unrank="${id}"]`]);
  toast(`Added ${shortName(room)} as choice ${state.queue.length}`, "You can change the order any time before you send it.", { icon: "playlist_add", position: toastWhere() });
}
function unrank(index) {
  if (index < 0) return;
  state.queue.splice(index, 1);
  saveDraft();
  update();
}
function move(index, dir) {
  const to = index + dir;
  if (to < 0 || to >= state.queue.length) return;
  [state.queue[index], state.queue[to]] = [state.queue[to], state.queue[index]];
  saveDraft();
  update();
  refocus([`[data-move="${to}"][data-dir="${dir}"]`, `[data-move="${to}"][data-dir="${-dir}"]`]);
}

// What to tell the student for each error the server can send back.
const ERROR_HINTS = {
  duplicate_room: "Remove the repeated choice, then send again.",
  empty_type: "Change that room type or remove it, then send again.",
  unknown_hostel: "Reload this page to get the current list of hostels.",
  unknown_room: "Reload this page to get the current list of rooms.",
  wrong_hostel_gender: "Remove that choice. You can only pick hostels you are allowed to live in.",
  own_room: "Remove your own room from the list.",
  no_seat: "Ask the hostel office to allocate you a room first.",
  too_many: `Keep at most ${MAX} choices.`,
  empty_list: "Add at least one choice.",
  invalid_input: "Reload this page and try again.",
};

function clearSubmitError() {
  const box = $("#submit-error");
  if (box) box.innerHTML = "";
}
function showSubmitError(error, title = "Your request wasn't sent") {
  const hint = ERROR_HINTS[error.code] || "Try again in a moment.";
  $("#submit-error").innerHTML = html`
    <div class="notice-bad" role="alert">
      <span class="material-symbols-outlined text-[18px] text-bad shrink-0" aria-hidden="true">error</span>
      <div class="flex flex-col gap-0.5 min-w-0">
        <span class="font-semibold text-ink">${title}</span>
        <span class="break-words">${error.message}</span>
        <span class="faint">${hint}</span>
      </div>
    </div>`;
}

async function submit(button) {
  if (locked() || !state.queue.length) return;
  clearSubmitError();
  const choices = state.queue.map((e) => (e.kind === "room"
    ? { room_id: e.room.id }
    : { type: { hostel: e.type.hostel, seater: e.type.seater, ac: e.type.ac, floor: e.type.floor } }));
  const restore = setBusy(button, "Sending…");
  try {
    const result = await api("/api/requests", { method: "POST", body: { choices } });
    state.queue = [];
    saveDraft();
    toast(`Request ${result.tracking_id} sent`, "Taking you to My swap…", { icon: "check_circle", position: toastWhere() });
    setTimeout(() => location.assign("/dashboard.html"), 1100);
  } catch (error) {
    restore();
    if (error.code === "already_active") {
      await load(); // shows the request that is already in the pool
      toast("You already have a request", "Withdraw it first if you want to send a new list.", { icon: "info", tone: "error", position: toastWhere() });
      return;
    }
    showSubmitError(error);
  }
}

async function secondary(button) {
  if (button.dataset.mode === "clear") {
    state.queue = [];
    saveDraft();
    update();
    return;
  }
  if (!confirm("Withdraw your request? It leaves the matching pool, and you can send a new list afterwards.")) return;
  const restore = setBusy(button, "Withdrawing…");
  try {
    await api("/api/requests/current", { method: "DELETE" });
    toast("Request withdrawn", "You can now build a new list.", { icon: "undo", position: toastWhere() });
    await load();
  } catch (error) {
    restore();
    showSubmitError(error, "Your request wasn't withdrawn");
  }
}

// ---------------------------------------------------------------- phone panel
function setPanelOpen(open) {
  const panel = $("#queue-panel");
  if (open && wide.matches) return;
  panel.classList.toggle("hidden", !open);
  for (const c of PANEL_OPEN) panel.classList.toggle(c, open);
  panel.setAttribute("role", open ? "dialog" : "complementary");
  if (open) panel.setAttribute("aria-modal", "true"); else panel.removeAttribute("aria-modal");
  document.body.classList.toggle("overflow-hidden", open);
  $("#phone-bar-btn").setAttribute("aria-expanded", String(open));
  if (open) panel.querySelector("[data-close-panel]")?.focus();
}
const panelOpen = () => !$("#queue-panel").classList.contains("hidden") && !wide.matches;

function setFiltersOpen(open) {
  const panel = $("#filter-panel");
  panel.classList.toggle("hidden", !open);
  panel.classList.toggle("flex", open);
  $("#filters-toggle").setAttribute("aria-expanded", String(open));
}

function wire() {
  document.addEventListener("click", (e) => {
    const t = e.target.closest("[data-rank],[data-unrank],[data-remove],[data-move],[data-clear],[data-page],[data-empty],[data-close-panel]");
    if (!t || t.disabled) return;
    if (t.dataset.rank) rank(Number(t.dataset.rank));
    else if (t.dataset.unrank) unrank(state.queue.findIndex((x) => x.kind === "room" && x.room.id === Number(t.dataset.unrank)));
    else if (t.dataset.remove) {
      const i = Number(t.dataset.remove);
      unrank(i);
      refocus([`[data-remove="${Math.min(i, state.queue.length - 1)}"]`, "[data-empty]"]);
    } else if (t.dataset.move) move(Number(t.dataset.move), Number(t.dataset.dir));
    else if (t.dataset.clear) clearFilter(t.dataset.clear);
    else if (t.dataset.page) { state.page = Number(t.dataset.page); renderList(); $("#rooms-heading").parentElement.scrollIntoView({ behavior: "smooth", block: "start" }); }
    else if (t.hasAttribute("data-close-panel")) { setPanelOpen(false); $("#phone-bar-btn").focus(); }
    else if (t.hasAttribute("data-empty")) {
      if (panelOpen()) setPanelOpen(false);
      $("#room-list").scrollIntoView({ behavior: "smooth", block: "start" });
    }
  });
  const onChange = (key) => (e) => { state.filters[key] = e.target.value; state.page = 1; update(); };
  $("#filter-hostel").addEventListener("change", onChange("hostel"));
  $("#filter-floor").addEventListener("change", onChange("floor"));
  $("#filter-seater").addEventListener("change", onChange("seater"));
  $("#search").addEventListener("input", onChange("search"));
  $("#sort").addEventListener("change", (e) => { state.sort = e.target.value; update(); });
  for (const b of $$("[data-toggle]")) {
    b.addEventListener("click", () => { state.filters[b.dataset.toggle] = !state.filters[b.dataset.toggle]; state.page = 1; syncControls(); update(); });
  }
  for (const [id, view] of [["#grid-view-btn", "grid"], ["#table-view-btn", "compact"]]) {
    $(id).addEventListener("click", () => {
      state.view = view;
      state.page = 1;
      $("#grid-view-btn").className = view === "grid" ? VIEW_ON : VIEW_OFF;
      $("#table-view-btn").className = view === "grid" ? VIEW_OFF : VIEW_ON;
      $("#grid-view-btn").setAttribute("aria-pressed", String(view === "grid"));
      $("#table-view-btn").setAttribute("aria-pressed", String(view !== "grid"));
      renderList();
    });
  }
  $("#filters-toggle").addEventListener("click", () => setFiltersOpen($("#filter-panel").classList.contains("hidden")));
  $("#lock-submit-btn").addEventListener("click", (e) => submit(e.currentTarget));
  $("#secondary-btn").addEventListener("click", (e) => secondary(e.currentTarget));

  // Room type form
  $("#type-toggle").addEventListener("click", () => setTypeFormOpen($("#type-form").hidden));
  $("#type-hostel").addEventListener("change", () => { fillTypeFloors(); renderTypePreview(); });
  for (const id of ["#type-seater", "#type-ac", "#type-floor"]) $(id).addEventListener("change", renderTypePreview);
  $("#type-form").addEventListener("submit", (e) => { e.preventDefault(); addType(); });

  // Phone panel
  $("#phone-bar-btn").addEventListener("click", () => setPanelOpen(true));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && panelOpen()) { setPanelOpen(false); $("#phone-bar-btn").focus(); }
  });
  wide.addEventListener("change", () => { if (wide.matches) setPanelOpen(false); });

  // Drag to reorder (mouse). Keyboard and touch use the arrow buttons.
  const box = $("#ranked-queue-container");
  let from = null;
  const clearMarks = () => $$(".queue-item", box).forEach((el) => el.classList.remove("opacity-50", "border-brass"));
  box.addEventListener("dragstart", (e) => {
    const item = e.target.closest(".queue-item[draggable]");
    if (!item) return;
    from = Number(item.dataset.index);
    item.classList.add("opacity-50");
    e.dataTransfer.effectAllowed = "move";
  });
  box.addEventListener("dragover", (e) => {
    const item = e.target.closest(".queue-item[draggable]");
    if (from === null || !item) return;
    e.preventDefault();
    $$(".queue-item", box).forEach((el) => el.classList.remove("border-brass"));
    item.classList.add("border-brass");
  });
  box.addEventListener("drop", (e) => {
    const item = e.target.closest(".queue-item[draggable]");
    if (from === null || !item) return;
    e.preventDefault();
    const to = Number(item.dataset.index);
    const [entry] = state.queue.splice(from, 1);
    state.queue.splice(to, 0, entry);
    from = null;
    saveDraft();
    update();
  });
  box.addEventListener("dragend", () => { from = null; clearMarks(); });
}

// ---------------------------------------------------------------- loading
function skeleton() {
  const list = $("#room-list");
  list.setAttribute("aria-busy", "true");
  list.innerHTML = Array.from({ length: 3 }, () => `<div class="card p-4 sm:p-5 flex flex-col gap-3" aria-hidden="true"><div class="flex justify-between gap-3"><div class="flex flex-col gap-2 flex-1"><div class="skeleton h-3 w-1/3 rounded-md"></div><div class="skeleton h-5 w-1/4 rounded-md"></div></div><div class="skeleton h-6 w-24 rounded-md"></div></div><div class="flex gap-1.5"><div class="skeleton h-6 w-20 rounded-md"></div><div class="skeleton h-6 w-14 rounded-md"></div><div class="skeleton h-6 w-32 rounded-md"></div></div><div class="flex justify-between items-center pt-3 border-t border-line"><div class="skeleton h-3 w-40 rounded-md"></div><div class="skeleton h-8 w-32 rounded-lg"></div></div></div>`).join("");
  $("#ranked-queue-container").innerHTML = Array.from({ length: 3 }, () => `<li class="skeleton h-12 rounded-lg" aria-hidden="true"></li>`).join("");
  $("#count-label").textContent = "Loading rooms…";
  $("#pagination").innerHTML = "";
  $("#lock-submit-btn").disabled = true;
}

async function load() {
  skeleton();
  try {
    const [listing, dashboard] = await Promise.all([api("/api/rooms"), api("/api/me/dashboard")]);
    state.rooms = listing.rooms;
    state.hostels = listing.hostels;
    state.lastRun = listing.last_run;
    state.request = dashboard.request;
    state.loaded = true;
    $("#filter-hostel").innerHTML = `<option value="">All hostels</option>`
      + listing.hostels.map((h) => html`<option value="${h.code}">${h.name}</option>`).join("");
    $("#filter-floor").innerHTML = `<option value="">Any floor</option>`
      + floorsOf("").map((f) => html`<option value="${f}">${floorLabel(f)}</option>`).join("");
    if (!state.hostels.some((h) => h.code === state.filters.hostel)) state.filters.hostel = "";
    if (state.filters.floor !== "" && !floorsOf("").includes(Number(state.filters.floor))) state.filters.floor = "";
    const typeHostel = $("#type-hostel").value;
    $("#type-hostel").innerHTML = listing.hostels.map((h) => html`<option value="${h.code}">${h.name}</option>`).join("");
    if (listing.hostels.some((h) => h.code === typeHostel)) $("#type-hostel").value = typeHostel;
    fillTypeFloors();
    if (!locked()) loadDraft();
    syncControls();
    renderYield();
    update();
  } catch (error) {
    if (error.status === 401) return location.replace("/");
    $("#room-list").setAttribute("aria-busy", "false");
    $("#count-label").textContent = "Rooms didn't load";
    $("#room-list").innerHTML = html`<div class="notice-bad" role="alert"><span class="material-symbols-outlined text-[18px] text-bad shrink-0" aria-hidden="true">error</span><div class="flex flex-col gap-1 min-w-0"><span class="font-semibold text-ink">Couldn't load rooms</span><span class="break-words">${error.message}</span><div><button class="btn-secondary btn-sm mt-2" id="retry" type="button">Try again</button></div></div></div>`;
    $("#ranked-queue-container").innerHTML = "";
    $("#yield-text").textContent = "Not available right now.";
    $("#phone-bar-text").textContent = "Rooms didn't load";
    $("#type-box").hidden = true;
    $("#lock-submit-btn").disabled = true;
    $("#retry").addEventListener("click", load);
  }
}

me = await requireUser("student");
fillHeader(me);
wire();
load();
