// Hostel staff page: two views on one page (#rooms and #slots).
// Room swaps: run TTC rounds (or dry runs), read the engine trace, approve
// confirmed chains, print approval forms, compare with 1:1 swaps, set automatic
// rounds. Lecture slots: the same for faculty slot swaps. Emails: the outbox.
import { api, requireUser } from "./api.js";
import { fillHeader } from "./nav.js";
import { $, $$, esc, formatDateTime, html, ordinal, plural, raw, setBusy, toast, toastError } from "./ui.js";

const PAGE_SIZE = 10;
const EMAILS_SHOWN = 10;
const MAX_EVERY_HOURS = 336; // the server allows 1 to 336 steps (14 days of hours)
const TABS = [
  ["all", "All"], ["open", "In pool"], ["matched", "In a swap"],
  ["awaiting", "Awaiting approval"], ["completed", "Approved"], ["withdrawn", "Withdrawn"],
];

const state = {
  view: "rooms",
  busy: false, // a round or comparison is running
  rooms: { overview: null, rows: [], loaded: false, filter: "all", search: "", page: 1, open: null },
  slots: { board: null, rows: [], loaded: false, loading: false, filter: "all", search: "", page: 1, open: null },
  schedule: null,
  timing: { demo: false, confirm: "48 hours", reminder: "12 hours" }, // replaced by the server's times at start
  emails: { data: null, showAll: false, open: new Set() },
};

// Icon sizes go in a style attribute: Tailwind cannot see class names built at run time.
const icon = (name, size = 18, extra = "") => `<span class="material-symbols-outlined ${extra}" style="font-size:${size}px" aria-hidden="true">${name}</span>`;
const istTime = (iso) => new Date(iso).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour12: false });
const pct = (part, whole) => (whole ? Math.round((part / whole) * 100) : 0);

function errorBlock(error, retry) {
  return html`<div class="notice-bad items-start">${raw(icon("error", 20, "text-bad shrink-0"))}
    <div class="flex flex-col gap-2 min-w-0"><span class="break-words">${error?.message || String(error)}</span>
    <button class="btn-secondary btn-sm self-start" data-retry="${retry}" type="button">Try again</button></div></div>`;
}

// ---------------------------------------------------------------- shared row pieces
const matchesFilter = (row, filter) => ({
  all: true,
  open: row.status === "open",
  matched: row.status === "matched",
  awaiting: Boolean(row.cycle?.can_approve),
  completed: row.status === "completed",
  withdrawn: row.status === "withdrawn",
})[filter];

function chainChip(cycle) {
  if (!cycle) return `<span class="faint">—</span>`;
  const n = cycle.length;
  return html`<span class="chip-neutral">${raw(icon(n === 2 ? "sync_alt" : "all_inclusive", 14))}${n === 2 ? "2-way direct" : `${n}-way loop`}</span>`;
}

function statusChip(row) {
  const c = row.cycle;
  if (row.status === "open") return `<span class="chip-info">In pool</span>`;
  if (row.status === "withdrawn") return `<span class="chip-neutral">Withdrawn</span>`;
  if (row.status === "completed") return `<span class="chip-ok">Approved</span>`;
  if (c?.status === "confirmed") return `<span class="chip-ok">Everyone confirmed</span>`;
  const waiting = c ? c.length - c.accepted : 0;
  return html`<span class="chip-warn">${waiting} still to answer</span>`;
}

function memberCard(m, i) {
  const answer = m.response === "accepted" ? ["text-ok", "Confirmed"] : m.response === "declined" ? ["text-bad", "Declined"] : ["text-brass", "Not answered yet"];
  return html`<div class="p-3 rounded-lg bg-panel border border-line min-w-0">
    <p class="text-xs faint">Member ${i + 1} · <span class="font-mono">${m.tracking_id}</span></p>
    <p class="font-semibold text-ink mt-1 truncate" title="${m.name}">${m.name}</p>
    <p class="text-xs muted mt-0.5 break-words">Gives <span class="font-mono">${m.gives}</span></p>
    <p class="text-xs font-semibold mt-1 ${raw(answer[0])}">${answer[1]}</p></div>`;
}

function detailPanel(row, { receivedRank, joinsText }) {
  const prefs = row.preferences.map((label, i) => {
    const got = receivedRank === i + 1;
    return html`<li class="flex items-center justify-between gap-2 px-2.5 py-1.5 rounded-md ${raw(got ? "bg-ok/10 border border-ok/30 text-ink" : "bg-panel border border-line text-ink-2")}">
      <span class="min-w-0 break-words"><span class="faint">${i + 1}.</span> ${label}</span>${got ? raw(`<span class="text-xs font-semibold text-ok shrink-0">Received</span>`) : ""}</li>`;
  });
  const c = row.cycle;
  return html`<div class="p-4 sm:p-5 bg-sunken/60 border-t border-line grid grid-cols-1 md:grid-cols-3 gap-4">
    <div class="min-w-0"><p class="text-sm font-semibold text-ink mb-2">Ranked choices</p>
      ${prefs.length ? raw(`<ol class="flex flex-col gap-1.5 text-sm">${prefs.join("")}</ol>`) : raw(`<p class="text-sm faint">No choices listed.</p>`)}</div>
    <div class="md:col-span-2 min-w-0 flex flex-col gap-2">
      <div class="flex items-center justify-between gap-2 flex-wrap"><p class="text-sm font-semibold text-ink">Swap chain</p>
        ${c ? raw(html`<span class="text-xs muted">Swap #${c.id} · ${c.accepted} of ${c.length} confirmed</span>`) : ""}</div>
      ${c ? raw(`<div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">${c.chain.map(memberCard).join("")}</div>`)
    : raw(html`<p class="text-sm muted">${joinsText}</p>`)}
    </div></div>`;
}

function expandCell(row, st) {
  const open = st.open === row.id;
  return html`<button class="inline-flex items-center gap-1 -ml-1 px-1 rounded-md font-mono text-[13px] text-ink hover:text-brass whitespace-nowrap" type="button"
    data-toggle="${row.id}" aria-expanded="${open}" aria-controls="detail-${st === state.slots ? "s" : "r"}-${row.id}">
    ${raw(icon(open ? "expand_less" : "expand_more", 18, "text-ink-3"))}${row.tracking_id}</button>`;
}

// ---------------------------------------------------------------- one table, two views
const TABLES = {
  rooms: {
    st: () => state.rooms, cols: 7, noun: "request",
    text: (r) => `${r.tracking_id} ${r.student.name} ${r.student.roll_no} ${r.offered_room} ${r.assigned_room || ""} ${r.preferences.join(" ")}`,
    cells: (r) => {
      const c = r.cycle;
      let action = "";
      if (c?.can_approve) action = html`<button class="btn-primary btn-sm" data-approve="room:${c.id}" type="button">${raw(icon("verified", 16))}Approve swap</button>`;
      else if (c?.status === "approved") action = html`<a class="btn-secondary btn-sm" href="/api/admin/cycles/${c.id}/approval.pdf" target="_blank" rel="noopener">${raw(icon("picture_as_pdf", 16))}Approval form (PDF)</a>`;
      const choice = r.received_rank
        ? html`<span class="${raw(r.received_rank === 1 ? "text-ok font-semibold" : "text-ink")}">${ordinal(r.received_rank)} choice</span><span class="faint"> of ${r.preferences.length}</span>`
        : html`<span class="faint">${plural(r.preferences.length, "room")} ranked</span>`;
      return html`
        <td>${raw(expandCell(r, state.rooms))}</td>
        <td><div class="flex items-center gap-2.5 min-w-0 max-w-[220px]"><span class="avatar">${r.student.initials}</span>
          <div class="min-w-0"><p class="font-semibold text-ink truncate" title="${r.student.name}">${r.student.name}</p><p class="text-xs faint truncate"><span class="font-mono">${r.student.roll_no}</span> · Year ${r.student.year}</p></div></div></td>
        <td><div class="flex flex-col gap-0.5"><span class="font-mono text-[13px] text-ink-2 whitespace-nowrap">${r.offered_room}</span>
          <span class="flex items-start gap-1">${raw(icon("arrow_downward", 14, "text-ink-3 mt-0.5"))}${r.assigned_room ? raw(html`<span class="font-mono text-[13px] text-ok whitespace-nowrap">${r.assigned_room}</span>`) : raw(`<span class="text-xs faint">Not matched yet</span>`)}</span></div></td>
        <td>${raw(chainChip(c))}</td>
        <td class="whitespace-nowrap">${raw(choice)}</td>
        <td>${raw(statusChip(r))}</td>
        <td class="text-right">${raw(action)}</td>`;
    },
    detail: (r) => detailPanel(r, { receivedRank: r.received_rank, joinsText: r.status === "open" ? "Not in a swap chain yet. This request joins the next matching round." : "Not in a swap chain." }),
    empty: () => state.rooms.rows.length
      ? "No requests match this filter or search. Try All, or clear the search."
      : "No students have asked for a room swap yet. Requests appear here as soon as students send them.",
  },
  slots: {
    st: () => state.slots, cols: 6, noun: "request",
    text: (r) => `${r.tracking_id} ${r.faculty.name} ${r.faculty.department} ${r.offered.label} ${r.offered.course_code} ${r.offered.course_name || ""} ${r.assigned || ""} ${r.preferences.join(" ")}`,
    cells: (r) => {
      const c = r.cycle;
      const action = c?.can_approve ? html`<button class="btn-primary btn-sm" data-approve="slot:${c.id}" type="button">${raw(icon("verified", 16))}Approve</button>` : "";
      return html`
        <td>${raw(expandCell(r, state.slots))}</td>
        <td><div class="flex items-center gap-2.5 min-w-0 max-w-[220px]"><span class="avatar">${r.faculty.initials}</span>
          <div class="min-w-0"><p class="font-semibold text-ink truncate" title="${r.faculty.name}">${r.faculty.name}</p><p class="text-xs faint truncate">${r.faculty.department}</p></div></div></td>
        <td><div class="flex flex-col gap-0.5 max-w-[280px]"><span class="text-ink-2 break-words"><span class="font-mono text-[13px]">${r.offered.label}</span> <span class="faint">· ${r.offered.course_code}</span></span>
          <span class="flex items-start gap-1">${raw(icon("arrow_downward", 14, "text-ink-3 mt-0.5"))}${r.assigned ? raw(html`<span class="font-mono text-[13px] text-ok break-words">${r.assigned}</span>`) : raw(`<span class="text-xs faint">Not matched yet</span>`)}</span></div></td>
        <td>${raw(chainChip(c))}</td>
        <td>${raw(statusChip(r))}</td>
        <td class="text-right">${raw(action)}</td>`;
    },
    detail: (r) => detailPanel(r, { receivedRank: r.assigned ? r.preferences.indexOf(r.assigned) + 1 || null : null, joinsText: r.status === "open" ? "Not in a swap chain yet. This request joins the next slot round." : "Not in a swap chain." }),
    empty: () => state.slots.rows.length
      ? "No requests match this filter or search. Try All, or clear the search."
      : "No teachers have asked to swap a lecture slot yet. Requests appear here as soon as faculty send them.",
  },
};

function visibleRows(kind) {
  const st = TABLES[kind].st();
  const q = st.search.trim().toLowerCase();
  return st.rows.filter((r) => matchesFilter(r, st.filter) && (!q || TABLES[kind].text(r).toLowerCase().includes(q)));
}

function renderTabs(kind) {
  const st = TABLES[kind].st();
  $(`#${kind}-tabs`).innerHTML = TABS.map(([key, label]) => {
    const count = st.rows.filter((r) => matchesFilter(r, key)).length;
    const on = st.filter === key;
    return html`<button class="h-8 px-3 rounded-lg text-sm whitespace-nowrap inline-flex items-center gap-1.5 transition-colors ${raw(on ? "bg-raised text-ink font-semibold" : "text-ink-2 hover:text-ink hover:bg-raised/60 font-medium")}"
      aria-pressed="${on}" data-filter="${kind}:${key}" type="button">${label}<span class="text-xs ${raw(key === "awaiting" && count ? "text-brass font-semibold" : "faint")}">${count}</span></button>`;
  }).join("");
}

function renderTable(kind) {
  const cfg = TABLES[kind];
  const st = cfg.st();
  renderTabs(kind);
  const rows = visibleRows(kind);
  const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  st.page = Math.min(st.page, pages);
  const slice = rows.slice((st.page - 1) * PAGE_SIZE, st.page * PAGE_SIZE);
  const prefix = kind === "slots" ? "s" : "r";
  $(`#${kind}-body`).innerHTML = slice.length
    ? slice.map((r) => html`<tr class="table-row ${raw(r.cycle?.can_approve ? "bg-brass/5" : "")}" data-row="${kind}:${r.id}">${raw(cfg.cells(r))}</tr>
        <tr id="detail-${prefix}-${r.id}" ${raw(st.open === r.id ? "" : "hidden")}><td class="p-0" colspan="${cfg.cols}">${raw(st.open === r.id ? cfg.detail(r) : "")}</td></tr>`).join("")
    : html`<tr><td class="px-4 py-12" colspan="${cfg.cols}"><div class="flex flex-col items-center text-center gap-2 max-w-sm mx-auto">
        ${raw(icon("inbox", 28, "text-ink-3"))}<p class="text-sm muted">${cfg.empty()}</p>
        ${st.rows.length && (st.filter !== "all" || st.search) ? raw(`<button class="btn-secondary btn-sm mt-1" data-clear="${kind}" type="button">Show all requests</button>`) : ""}</div></td></tr>`;
  const from = rows.length ? (st.page - 1) * PAGE_SIZE + 1 : 0;
  const to = Math.min(rows.length, st.page * PAGE_SIZE);
  const pageBtn = (p, { arrow = null, disabled = false } = {}) => {
    const current = !arrow && p === st.page;
    const label = arrow === "prev" ? "Previous page" : arrow === "next" ? "Next page" : `Page ${p}`;
    const inner = arrow ? icon(arrow === "prev" ? "chevron_left" : "chevron_right", 18) : esc(p);
    return html`<button class="h-8 min-w-8 px-2 inline-flex items-center justify-center rounded-lg text-sm transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${raw(current ? "bg-raised text-ink font-semibold" : "text-ink-2 hover:bg-raised")}"
      data-page="${kind}:${p}" type="button" aria-label="${label}" ${raw(disabled ? "disabled" : "")} ${raw(current ? 'aria-current="page"' : "")}>${raw(inner)}</button>`;
  };
  $(`#${kind}-footer`).innerHTML = html`<p class="text-xs faint">Showing ${from}–${to} of ${plural(rows.length, cfg.noun)}</p>`
    + (pages > 1 ? `<div class="flex items-center gap-1 flex-wrap">${pageBtn(st.page - 1, { arrow: "prev", disabled: st.page === 1 })}${Array.from({ length: pages }, (_, i) => pageBtn(i + 1)).join("")}${pageBtn(st.page + 1, { arrow: "next", disabled: st.page === pages })}</div>` : "");
}

function tableError(kind, error) {
  $(`#${kind}-tabs`).innerHTML = "";
  $(`#${kind}-footer`).innerHTML = "";
  $(`#${kind}-body`).innerHTML = html`<tr><td class="p-4" colspan="${TABLES[kind].cols}">${raw(errorBlock(error, kind))}</td></tr>`;
}

function tableNotice(kind, error) {
  $(`#${kind}-table-notice`).innerHTML = error ? html`<div class="px-4 pt-4"><div class="notice-bad items-start">${raw(icon("error", 20, "text-bad shrink-0"))}
    <span class="flex-1 min-w-0 break-words">${error.message}</span>
    <button class="icon-btn w-7 h-7 -my-1 shrink-0" data-dismiss="${kind}" type="button" aria-label="Dismiss">${raw(icon("close", 18))}</button></div></div>` : "";
}

// ---------------------------------------------------------------- trace
function traceTag(line) {
  const t = line.trim();
  if (t.startsWith("Pool:")) return ["Start", "text-info"];
  if (t.startsWith("Round")) return ["Round", "text-ink-2"];
  if (t.includes("Chain found")) return ["Chain", "text-ok"];
  if (t.includes("keep their")) return ["Kept", "text-ink-3"];
  if (t.startsWith("Matched")) return ["Result", "text-ok"];
  return ["Note", "text-ink-3"];
}

function renderTrace(kind, trace, run, label, emptyText) {
  const box = $(`#${kind}-trace`);
  const lines = (trace || "").split("\n").filter((l) => l.trim());
  $(`#${kind}-trace-chip`).textContent = run && lines.length ? label : "No run yet";
  if (!lines.length) {
    box.innerHTML = html`<p class="font-sans text-sm faint">${emptyText}</p>`;
    return;
  }
  const time = run ? istTime(run.created_at) : "";
  box.innerHTML = lines.map((line) => {
    const [tag, tone] = traceTag(line);
    return html`<div class="flex items-start gap-3 ${raw(tag === "Result" ? "font-semibold text-ink" : "text-ink-2")}">
      <span class="hidden sm:inline text-ink-3 shrink-0">${time}</span><span class="${raw(tone)} shrink-0 w-14">${tag}</span><span class="min-w-0 whitespace-pre-wrap break-words">${line.trim()}</span></div>`;
  }).join("");
}

function runLabel(run) {
  if (!run) return "";
  if (run.algorithm === "pairwise") return `Run #${run.id} · 1:1 comparison`;
  return `Run #${run.id} · ${run.dry_run ? "dry run" : "saved"} · ${formatDateTime(run.created_at)}`;
}

// ---------------------------------------------------------------- room swaps view
function kpiCard(filter, { label, value, unit, sub, bar, barTone, foot }) {
  const on = state.rooms.filter === filter;
  return html`<button class="card card-pad text-left flex flex-col gap-3 transition-colors hover:border-line-strong ${raw(on ? "border-brass/50 bg-raised/40" : "")}"
    data-filter="rooms:${filter}" aria-pressed="${on}" type="button">
    <span class="text-sm font-medium muted">${label}</span>
    <span class="flex items-baseline gap-2 min-w-0"><span class="text-2xl font-bold text-ink">${value}</span><span class="text-xs faint truncate">${unit}</span></span>
    ${raw(sub ? html`<span class="text-xs muted">${sub}</span>` : "")}
    ${raw(bar === null ? "" : html`<span class="block w-full h-1.5 rounded-full bg-raised overflow-hidden"><span class="block h-full rounded-full ${raw(barTone)}" style="width:${bar}%"></span></span>`)}
    <span class="text-xs faint">${raw(foot)}</span></button>`;
}

function renderKpis() {
  const o = state.rooms.overview;
  const latest = o.latest;
  const lengths = latest?.cycles_by_length || {};
  const two = Number(lengths["2"] || 0);
  const multi = Object.entries(lengths).filter(([k]) => Number(k) >= 3).sort(([a], [b]) => a - b);
  const multiLoops = multi.reduce((s, [, v]) => s + v, 0);
  const multiStudents = multi.reduce((s, [k, v]) => s + Number(k) * v, 0);
  const total = o.open + o.matched + o.completed;
  $("#kpi-grid").innerHTML = [
    kpiCard("open", { label: "Students in the pool", value: o.open, unit: "open requests", bar: pct(o.open, total), barTone: "bg-info",
      foot: esc(`${o.matched} in a swap · ${o.completed} approved`) }),
    kpiCard("matched", { label: "Direct 2-way swaps", value: latest ? two : "—", unit: latest ? plural(two * 2, "student") : "no saved round yet",
      bar: latest ? pct(two * 2, latest.matched) : null, barTone: "bg-ok",
      foot: latest ? esc(`${pct(two * 2, latest.matched)}% of matched students, last saved round`) : "Run a round to see this" }),
    kpiCard("matched", { label: "Multi-way loops", value: latest ? multiLoops : "—", unit: latest ? plural(multiStudents, "student") : "no saved round yet",
      bar: latest ? pct(multiStudents, latest.matched) : null, barTone: "bg-ok",
      foot: latest ? (multi.length ? esc(multi.map(([k, v]) => `${k}-way: ${v}`).join(" · ")) : "None in the last saved round") : "Only Top Trading Cycles finds these" }),
    kpiCard("all", { label: "Match yield", value: latest ? `${latest.yield_pct}%` : "—", unit: latest ? `${latest.matched} of ${latest.pool_size} matched` : "no saved round yet",
      bar: latest ? latest.yield_pct : null, barTone: "bg-ok",
      foot: latest ? esc(`Got their first choice: ${latest.first_choice_pct}%`) : "Share of the pool placed in a swap" }),
  ].join("");
}

function renderAwaiting(kind, count) {
  $(`#${kind}-awaiting`).innerHTML = count ? html`<div class="notice-warn items-center flex-wrap">${raw(icon("pending_actions", 20, "text-brass shrink-0"))}
    <span class="flex-1 min-w-[12rem]"><strong class="text-ink font-semibold">${plural(count, "swap")}</strong> ${count === 1 ? "is" : "are"} confirmed by everyone and waiting for your approval.</span>
    <button class="btn-secondary btn-sm" data-filter="${kind}:awaiting" data-scroll="${kind}" type="button">Show ${count === 1 ? "it" : "them"}</button></div>` : "";
}

function renderComparison() {
  const c = state.rooms.overview.comparison;
  const target = $("#comparison");
  if (!c) {
    target.innerHTML = `<p class="text-sm muted">No comparison yet. Press the button below. Both methods run as dry runs on today's pool, so nothing changes for students.</p>`;
    return;
  }
  const bar = (label, value, tone) => html`<div class="flex flex-col gap-1.5"><div class="flex items-center justify-between gap-2 text-sm"><span class="text-ink">${label}</span><span class="font-semibold text-ink">${value}%</span></div>
    <div class="w-full h-2 rounded-full bg-raised overflow-hidden"><div class="h-full rounded-full ${raw(tone)}" style="width:${Math.min(100, Math.max(value, 1))}%"></div></div></div>`;
  const diff = Math.round((c.ttc - c.pairwise) * 10) / 10;
  target.innerHTML = bar("Top Trading Cycles", c.ttc, "bg-brass") + bar("1:1 swaps only", c.pairwise, "bg-ink-3")
    + html`<div class="flex items-center justify-between gap-3 p-3 rounded-lg bg-sunken border border-line"><span class="text-sm muted">Extra share of the pool matched by multi-way chains</span><span class="${raw(diff > 0 ? "chip-ok" : "chip-neutral")}">${diff > 0 ? "+" : ""}${diff} points</span></div>`;
}

function renderRooms() {
  const o = state.rooms.overview;
  $("#rooms-meta").textContent = o.latest ? `Last saved round: ${formatDateTime(o.latest.created_at)} IST` : "No saved round yet. Run one when the pool is ready.";
  renderAwaiting("rooms", o.awaiting_approval);
  renderKpis();
  renderTable("rooms");
  renderComparison();
}

function showRoomsTrace() {
  const o = state.rooms.overview;
  // The server's "latest trace" is the latest run of any kind, slot rounds included.
  if (o.trace_run?.algorithm === "slot_ttc") {
    $("#rooms-trace-chip").textContent = "No room run to show";
    $("#rooms-trace").innerHTML = `<p class="font-sans text-sm faint">The latest run was a lecture slot round. Its trace is in the Lecture slots view. Run a room round or a dry run to see a room trace here.</p>`;
    return;
  }
  renderTrace("rooms", o.trace, o.trace_run, runLabel(o.trace_run), "No round has run yet. Press Run matching round to start one.");
}

async function loadRooms({ keepTrace = false } = {}) {
  try {
    const [overview, rows] = await Promise.all([api("/api/admin/overview"), api("/api/admin/requests")]);
    state.rooms.overview = overview;
    state.rooms.rows = rows;
    state.rooms.loaded = true;
    renderRooms();
    if (!keepTrace) showRoomsTrace();
  } catch (error) {
    if (state.rooms.loaded) return toastError(error);
    $("#rooms-meta").textContent = "Could not load the room swap data.";
    $("#kpi-grid").innerHTML = `<div class="sm:col-span-2 lg:col-span-4">${errorBlock(error, "rooms")}</div>`;
    tableError("rooms", error);
    $("#rooms-trace").innerHTML = `<p class="font-sans text-sm faint">The trace appears once the page has loaded.</p>`;
    $("#comparison").innerHTML = `<p class="text-sm faint">The comparison appears once the page has loaded.</p>`;
  }
}

// ---------------------------------------------------------------- lecture slots view
function slotKpi(filter, label, value, unit, foot) {
  const on = state.slots.filter === filter;
  return html`<button class="card card-pad text-left flex flex-col gap-2 transition-colors hover:border-line-strong min-w-0 ${raw(on ? "border-brass/50 bg-raised/40" : "")}"
    data-filter="slots:${filter}" aria-pressed="${on}" type="button">
    <span class="text-sm font-medium muted">${label}</span>
    <span class="flex items-baseline gap-2 min-w-0"><span class="text-2xl font-bold text-ink">${value}</span><span class="text-xs faint truncate">${unit}</span></span>
    <span class="text-xs faint">${foot}</span></button>`;
}

function renderSlots() {
  const b = state.slots.board;
  const latest = b.latest;
  renderAwaiting("slots", b.awaiting_approval);
  $("#slots-kpis").innerHTML = [
    slotKpi("open", "Open requests", b.open, "in the pool", "Join the next slot round"),
    slotKpi("awaiting", "Awaiting approval", b.awaiting_approval, plural(b.awaiting_approval, "swap"), "Everyone confirmed, needs you"),
    slotKpi("all", "Last slot round", latest ? `${latest.yield_pct}%` : "—", latest ? `${latest.matched} of ${latest.pool_size} matched` : "no round yet",
      latest ? `${latest.dry_run ? "Dry run" : "Saved"} · ${formatDateTime(latest.created_at)} IST` : "Run one to see the result"),
  ].join("");
  renderTable("slots");
}

function showSlotsTrace() {
  const b = state.slots.board;
  renderTrace("slots", b.trace, b.latest, runLabel(b.latest), "No slot round has run yet. Press Run slot round to start one.");
}

async function loadSlots({ keepTrace = false } = {}) {
  state.slots.loading = true;
  try {
    const board = await api("/api/admin/slots");
    state.slots.board = board;
    state.slots.rows = board.requests;
    state.slots.loaded = true;
    renderSlots();
    if (!keepTrace) showSlotsTrace();
  } catch (error) {
    if (state.slots.loaded) return toastError(error);
    $("#slots-kpis").innerHTML = `<div class="sm:col-span-3">${errorBlock(error, "slots")}</div>`;
    tableError("slots", error);
    $("#slots-trace").innerHTML = `<p class="font-sans text-sm faint">The trace appears once the page has loaded.</p>`;
  } finally {
    state.slots.loading = false;
  }
}

// ---------------------------------------------------------------- automatic rounds
function renderSchedule() {
  const s = state.schedule;
  const unit = s.unit || "hour";
  const next = s.enabled && s.next_run_at ? `Next round: ${formatDateTime(s.next_run_at)} IST` : "Off";
  $("#schedule-body").innerHTML = html`<form class="flex flex-col gap-4" id="schedule-form" novalidate>
    <div class="flex items-center justify-between gap-4">
      <span class="min-w-0"><span class="block text-sm font-medium text-ink" id="sched-on-label">Run rounds automatically</span>
        <span class="block text-xs faint mt-0.5">Each automatic round is saved, like pressing Run.</span></span>
      <button class="relative inline-flex w-11 h-6 shrink-0 rounded-full border transition-colors ${raw(s.enabled ? "bg-brass border-brass" : "bg-raised border-line-strong")}"
        id="sched-on" role="switch" aria-checked="${s.enabled}" aria-labelledby="sched-on-label" type="button">
        <span class="absolute top-0.5 left-0.5 w-[18px] h-[18px] rounded-full transition-transform ${raw(s.enabled ? "translate-x-5 bg-brass-ink" : "bg-ink-2")}"></span></button>
    </div>
    <div>
      <label class="label" for="sched-hours">Every how many ${unit}s</label>
      <div class="flex items-center gap-3 flex-wrap">
        <input class="field w-28" id="sched-hours" type="number" inputmode="numeric" min="1" max="${MAX_EVERY_HOURS}" step="1" value="${s.every_hours}" aria-describedby="sched-hours-hint sched-error"/>
        <span class="text-xs faint" id="sched-hours-hint">1 to ${MAX_EVERY_HOURS} ${unit}s${unit === "hour" ? " (14 days)" : ""}</span>
      </div>
      <p class="text-xs text-bad mt-1.5" id="sched-error" hidden></p>
    </div>
    <div class="flex items-center justify-between gap-3 flex-wrap pt-1">
      <span class="text-sm min-w-0"><span class="${raw(s.enabled ? "text-ink font-medium" : "muted")}">${next}</span>${s.set_by ? raw(html`<span class="faint"> · set by ${s.set_by}</span>`) : ""}</span>
      <button class="btn-primary" id="btn-sched-save" type="submit">Save schedule</button>
    </div></form>`;
}

async function loadSchedule() {
  try {
    state.schedule = await api("/api/admin/schedule");
    renderSchedule();
  } catch (error) {
    $("#schedule-body").innerHTML = errorBlock(error, "schedule");
  }
}

async function saveSchedule(e) {
  e.preventDefault();
  const hoursEl = $("#sched-hours");
  const errEl = $("#sched-error");
  const enabled = $("#sched-on").getAttribute("aria-checked") === "true";
  const hours = Number(hoursEl.value);
  if (!Number.isInteger(hours) || hours < 1 || hours > MAX_EVERY_HOURS) {
    errEl.textContent = `Enter a whole number of ${state.schedule.unit || "hour"}s from 1 to ${MAX_EVERY_HOURS}.`;
    errEl.hidden = false;
    hoursEl.setAttribute("aria-invalid", "true");
    hoursEl.focus();
    return;
  }
  const done = setBusy($("#btn-sched-save"), "Saving…");
  try {
    state.schedule = await api("/api/admin/schedule", { method: "PUT", body: { enabled, every_hours: hours } });
    renderSchedule();
    toast(enabled ? "Automatic rounds are on" : "Automatic rounds are off",
      enabled ? `A saved round runs every ${plural(hours, state.schedule.unit || "hour")}. Next: ${formatDateTime(state.schedule.next_run_at)} IST.` : "Rounds run only when someone presses Run.");
  } catch (error) {
    done();
    errEl.textContent = error.message;
    errEl.hidden = false;
  }
}

// ---------------------------------------------------------------- emails
function emailChip(e) {
  if (e.status === "sent") return `<span class="chip-ok">Sent</span>`;
  if (e.error) return `<span class="chip-bad">Failed, will retry</span>`;
  return `<span class="chip-warn">Queued</span>`;
}

function renderEmails() {
  const { data, showAll, open } = state.emails;
  const notice = data.delivery === "off"
    ? html`<div class="notice-warn items-start">${raw(icon("warning", 20, "text-brass shrink-0"))}<span>Email sending is not set up on this server, so these emails are queued, not sent. Set <span class="code">CAMPUSSWAP_SMTP_HOST</span> to send them.</span></div>`
    : html`<p class="text-xs faint">Emails are sent through the mail server set in <span class="code">CAMPUSSWAP_SMTP_HOST</span>.</p>`;
  if (!data.emails.length) {
    $("#emails-body").innerHTML = html`<div class="card-pad flex flex-col gap-4">${raw(notice)}
      <div class="flex flex-col items-center text-center gap-2 py-6">${raw(icon("mail", 28, "text-ink-3"))}
      <p class="text-sm muted max-w-sm">No emails yet. CampusSwap writes one to each person when a round puts them in a swap, and a reminder ${state.timing.reminder} before their deadline.</p></div></div>`;
    return;
  }
  const list = showAll ? data.emails : data.emails.slice(0, EMAILS_SHOWN);
  const items = list.map((e) => html`<li class="border-t border-line first:border-t-0">
    <details data-email="${e.id}" ${raw(open.has(e.id) ? "open" : "")}>
      <summary class="list-none [&::-webkit-details-marker]:hidden cursor-pointer px-5 py-3 hover:bg-raised/40 grid grid-cols-[minmax(0,1fr)_auto] sm:grid-cols-[minmax(0,14rem)_minmax(0,1fr)_auto_auto] items-center gap-x-4 gap-y-1">
        <span class="text-sm text-ink truncate" title="${e.to}">${e.to}</span>
        <span class="sm:order-none order-last col-span-2 sm:col-span-1 text-sm muted truncate" title="${e.subject}">${e.subject}</span>
        <span class="justify-self-end">${raw(emailChip(e))}</span>
        <span class="hidden sm:inline text-xs faint whitespace-nowrap">${formatDateTime(e.created_at)}</span>
      </summary>
      <div class="px-5 pb-4 flex flex-col gap-2">
        <p class="text-xs faint">Written ${formatDateTime(e.created_at)} IST${e.sent_at ? ` · sent ${formatDateTime(e.sent_at)} IST` : ""}${e.attempts ? ` · ${plural(e.attempts, "attempt")}` : ""}</p>
        ${e.error ? raw(html`<p class="text-xs text-bad break-words">Last error: ${e.error}</p>`) : ""}
        <pre class="font-sans text-sm text-ink-2 whitespace-pre-wrap break-words bg-sunken border border-line rounded-lg p-3">${e.body}</pre>
      </div>
    </details></li>`).join("");
  const more = data.emails.length > EMAILS_SHOWN
    ? html`<div class="px-5 py-3 border-t border-line"><button class="btn-ghost btn-sm" data-emails-more type="button">${showAll ? "Show fewer" : `Show all ${data.emails.length}`}</button></div>` : "";
  $("#emails-body").innerHTML = html`<div class="px-5 pt-4 pb-3">${raw(notice)}</div><ul class="border-t border-line">${raw(items)}</ul>${raw(more)}`;
}

async function loadEmails() {
  try {
    state.emails.data = await api("/api/admin/emails");
    renderEmails();
  } catch (error) {
    $("#emails-body").innerHTML = `<div class="card-pad">${errorBlock(error, "emails")}</div>`;
  }
}

// ---------------------------------------------------------------- actions
function setRunLabels() {
  // While a button shows "Running…" its label span is gone; it is set again when the run ends.
  const room = $("#btn-run [data-run-label]"), slot = $("#btn-slot-run [data-run-label]");
  if (room) room.textContent = $("#rooms-dry").checked ? "Preview round (dry run)" : "Run matching round";
  if (slot) slot.textContent = $("#slots-dry").checked ? "Preview slot round (dry run)" : "Run slot round";
}

async function runRoomRound() {
  if (state.busy) return;
  const dry = $("#rooms-dry").checked;
  if (!dry && !confirm(`Run a real matching round now? Students placed in swap chains get ${state.timing.confirm} to confirm, and an email is written to each of them.`)) return;
  state.busy = true;
  const done = setBusy($("#btn-run"), "Running round…");
  $("#btn-compare").disabled = true;
  try {
    const run = await api("/api/admin/match-runs", { method: "POST", body: { algorithm: "ttc", dry_run: dry } });
    renderTrace("rooms", run.trace, run, runLabel(run), "");
    toast(dry ? `Dry run: would match ${run.matched} of ${run.pool_size}` : `Round #${run.id}: matched ${run.matched} of ${run.pool_size}`,
      `Match yield ${run.yield_pct}%${dry ? ". Nothing was saved." : ". Students can now confirm."}`);
    await Promise.all([loadRooms({ keepTrace: true }), dry ? null : loadEmails()]);
  } catch (error) {
    toastError(error);
  } finally {
    state.busy = false;
    done();
    $("#btn-compare").disabled = false;
    setRunLabels();
  }
}

async function compare() {
  if (state.busy) return;
  state.busy = true;
  const done = setBusy($("#btn-compare"), "Comparing…");
  $("#btn-run").disabled = true;
  try {
    const result = await api("/api/admin/compare", { method: "POST" });
    renderTrace("rooms", `${result.ttc.trace}\n${result.pairwise.trace}`, result.ttc, `Comparison · runs #${result.ttc.id} and #${result.pairwise.id}`, "");
    toast("Comparison finished", `Top Trading Cycles ${result.ttc.yield_pct}% vs 1:1 only ${result.pairwise.yield_pct}%. Nothing was saved.`);
    await loadRooms({ keepTrace: true });
  } catch (error) {
    toastError(error);
  } finally {
    state.busy = false;
    done();
    $("#btn-run").disabled = false;
  }
}

async function runSlotRound() {
  if (state.busy) return;
  const dry = $("#slots-dry").checked;
  if (!dry && !confirm(`Run a real slot round now? Teachers placed in swap chains get ${state.timing.confirm} to confirm, and an email is written to each of them.`)) return;
  state.busy = true;
  const done = setBusy($("#btn-slot-run"), "Running slot round…");
  try {
    const run = await api("/api/admin/slot-runs", { method: "POST", body: { dry_run: dry } });
    renderTrace("slots", run.trace, run, runLabel(run), "");
    toast(dry ? `Dry run: would match ${run.matched} of ${run.pool_size}` : `Slot round #${run.id}: matched ${run.matched} of ${run.pool_size}`,
      `Match yield ${run.yield_pct}%${dry ? ". Nothing was saved." : ". Teachers can now confirm."}`);
    await Promise.all([loadSlots({ keepTrace: true }), dry ? null : loadEmails()]);
  } catch (error) {
    toastError(error);
  } finally {
    state.busy = false;
    done();
    setRunLabels();
  }
}

async function approve(button, kind, cycleId) {
  const rooms = kind === "room";
  if (state.busy) return; // a round is running: its result may change this swap
  if (!confirm(rooms ? `Approve swap #${cycleId}? The students' rooms change in CampusSwap's records.` : `Approve slot swap #${cycleId}? The lecture slots change hands in the timetable.`)) return;
  const done = setBusy(button, "Approving…");
  const view = rooms ? "rooms" : "slots";
  tableNotice(view, null);
  try {
    await api(rooms ? `/api/admin/cycles/${cycleId}/approve` : `/api/admin/slot-cycles/${cycleId}/approve`, { method: "POST" });
    toast(rooms ? `Swap #${cycleId} approved` : `Slot swap #${cycleId} approved`,
      rooms ? "The rooms have changed hands. The approval form is ready to print." : "The slots have changed hands in the timetable.", { icon: "verified" });
  } catch (error) {
    tableNotice(view, error); // e.g. stale_swap: the swap was cancelled, the others are back in the pool
    toastError(error);
  } finally {
    done(); // the reload below redraws the table; if it fails, the button still comes back
  }
  await (rooms ? loadRooms({ keepTrace: true }) : loadSlots({ keepTrace: true }));
}

// ---------------------------------------------------------------- views (#rooms / #slots)
function showView() {
  state.view = location.hash === "#slots" ? "slots" : "rooms";
  for (const section of $$("[data-view]")) section.hidden = section.dataset.view !== state.view;
  for (const link of $$("[data-view-link]")) {
    if (link.dataset.viewLink === state.view) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
  document.title = `CampusSwap · ${state.view === "slots" ? "Lecture slots" : "Room swaps"}`;
  if (state.view === "slots" && !state.slots.loaded && !state.slots.loading) loadSlots();
}

function wire() {
  document.addEventListener("click", (e) => {
    const t = e.target.closest("[data-filter],[data-page],[data-toggle],[data-approve],[data-retry],[data-clear],[data-dismiss],[data-emails-more],[data-row]");
    if (!t) return;
    if (t.dataset.approve) {
      const [kind, id] = t.dataset.approve.split(":");
      return approve(t, kind, Number(id));
    }
    if (t.dataset.retry) {
      const r = t.dataset.retry;
      if (r === "rooms") { $("#kpi-grid").innerHTML = '<div class="skeleton h-[148px]"></div>'.repeat(4); return loadRooms(); }
      if (r === "slots") { $("#slots-kpis").innerHTML = '<div class="skeleton h-[124px]"></div>'.repeat(3); return loadSlots(); }
      if (r === "schedule") { $("#schedule-body").innerHTML = '<div class="skeleton h-28"></div>'; return loadSchedule(); }
      if (r === "emails") { $("#emails-body").innerHTML = '<div class="p-5"><div class="skeleton h-28"></div></div>'; return loadEmails(); }
    }
    if (t.dataset.dismiss) return tableNotice(t.dataset.dismiss, null);
    if (t.hasAttribute("data-emails-more")) { state.emails.showAll = !state.emails.showAll; return renderEmails(); }
    if (t.dataset.clear) {
      const st = TABLES[t.dataset.clear].st();
      st.filter = "all"; st.search = ""; st.page = 1;
      $(`#${t.dataset.clear}-search`).value = "";
      return t.dataset.clear === "rooms" ? renderRooms() : renderSlots();
    }
    if (t.dataset.filter) {
      const [kind, filter] = t.dataset.filter.split(":");
      const st = TABLES[kind].st();
      st.filter = filter; st.page = 1;
      kind === "rooms" ? renderKpis() : renderSlots();
      renderTable(kind);
      if (t.dataset.scroll) $(`#${kind}-body`).closest(".card").scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    if (t.dataset.page) {
      const [kind, p] = t.dataset.page.split(":");
      TABLES[kind].st().page = Number(p);
      return renderTable(kind);
    }
    // Expand a row: the ID button, or a click anywhere on the row that is not a link or button.
    const key = t.dataset.toggle ? `${t.closest("[data-row]").dataset.row}` : t.dataset.row;
    if (!t.dataset.toggle && e.target.closest("a,button")) return;
    const [kind, id] = key.split(":");
    const st = TABLES[kind].st();
    st.open = st.open === Number(id) ? null : Number(id);
    renderTable(kind);
    $(`[data-row="${kind}:${id}"] [data-toggle]`)?.focus();
  });
  for (const kind of ["rooms", "slots"]) {
    $(`#${kind}-search`).addEventListener("input", (e) => {
      const st = TABLES[kind].st();
      st.search = e.target.value; st.page = 1;
      if (st.loaded) renderTable(kind);
    });
  }
  $("#btn-run").addEventListener("click", runRoomRound);
  $("#btn-compare").addEventListener("click", compare);
  $("#btn-slot-run").addEventListener("click", runSlotRound);
  $("#rooms-dry").addEventListener("change", setRunLabels);
  $("#slots-dry").addEventListener("change", setRunLabels);
  $("#btn-emails-refresh").addEventListener("click", async (e) => {
    const done = setBusy(e.currentTarget, "Refreshing…");
    await loadEmails();
    done();
  });
  // Schedule form: the switch flips locally; nothing is saved until "Save schedule".
  $("#schedule-body").addEventListener("click", (e) => {
    const sw = e.target.closest("#sched-on");
    if (!sw) return;
    const on = sw.getAttribute("aria-checked") !== "true";
    sw.setAttribute("aria-checked", String(on));
    sw.className = `relative inline-flex w-11 h-6 shrink-0 rounded-full border transition-colors ${on ? "bg-brass border-brass" : "bg-raised border-line-strong"}`;
    sw.firstElementChild.className = `absolute top-0.5 left-0.5 w-[18px] h-[18px] rounded-full transition-transform ${on ? "translate-x-5 bg-brass-ink" : "bg-ink-2"}`;
  });
  $("#schedule-body").addEventListener("submit", saveSchedule);
  $("#schedule-body").addEventListener("input", (e) => {
    if (e.target.id !== "sched-hours") return;
    $("#sched-error").hidden = true;
    e.target.removeAttribute("aria-invalid");
  });
  // Remember which emails are open across refreshes.
  $("#emails-body").addEventListener("toggle", (e) => {
    const id = Number(e.target.dataset?.email);
    if (!id) return;
    e.target.open ? state.emails.open.add(id) : state.emails.open.delete(id);
  }, true);
  window.addEventListener("hashchange", showView);
}

// Demo mode (run.py --demo) shortens every wait; say so and use the server's times in the text.
function applyTiming() {
  const t = state.timing;
  for (const el of $$("[data-confirm-time]")) el.textContent = t.confirm;
  $("#demo-note").hidden = !t.demo;
  if (t.demo) $("#demo-note-text").textContent = `Demo mode: times are shortened. Chains have ${t.confirm} to confirm, the reminder email goes ${t.reminder} before the deadline, and automatic rounds count in minutes.`;
}

const me = await requireUser("admin");
fillHeader(me);
state.timing = await api("/api/public/stats").then((s) => s.timing || state.timing, () => state.timing);
applyTiming();
wire();
setRunLabels();
showView();
loadRooms();
loadSchedule();
loadEmails();
