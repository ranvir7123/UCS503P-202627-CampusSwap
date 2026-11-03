// Draws a swap chain of any length (2, 3, 4, ...): one card per member placed
// around a loop on wide screens, joined by arrows that point from each student
// to the room they move into. On phones and tablets the same cards stack
// top to bottom with a "moves into" connector between them.
import { html, raw } from "./ui.js";

const first = (name) => String(name || "").split(" ")[0];
const floorText = (floor) => (floor === 0 ? "Ground floor" : `Floor ${floor}`);

export function roomDetails(room) {
  const parts = [`${room.seater}-seater`, room.ac ? "AC" : "Non-AC", room.washroom === "attached" ? "Attached bath" : "Common bath", floorText(room.floor)];
  return parts.join(" · ");
}

const RESPONSE = {
  accepted: ["chip-ok", "check", "Confirmed"],
  pending: ["chip-warn", "schedule", "Waiting"],
  declined: ["chip-bad", "close", "Declined"],
};

export function responseChip(response) {
  const [cls, icon, label] = RESPONSE[response] || RESPONSE.pending;
  return html`<span class="${raw(cls)}"><span class="material-symbols-outlined text-[14px]" aria-hidden="true">${icon}</span>${label}</span>`;
}

// The signed-in student goes first, then the chain in order. Member i moves
// into the room of member i + 1 (the last one moves into the first one's room).
function ordered(cycle) {
  const list = [...cycle.members].sort((a, b) => a.position - b.position);
  const me = list.findIndex((m) => m.is_me);
  return me > 0 ? [...list.slice(me), ...list.slice(0, me)] : list;
}

function memberCard(member, next) {
  const owner = next.is_me ? "your room" : `${first(next.name)}'s room`;
  const tone = member.is_me ? "bg-raised border-brass" : "bg-panel border-line";
  return html`
  <article class="ring-card w-full lg:w-64 ${raw(tone)} border rounded-xl p-4 flex flex-col gap-3 min-w-0"
    aria-label="${member.is_me ? "You" : member.name}: ${RESPONSE[member.response]?.[2] || "Waiting"}">
    <div class="flex items-start gap-3 min-w-0">
      <div class="avatar ${raw(member.is_me ? "border-brass text-brass" : "")}" aria-hidden="true">${member.initials}</div>
      <div class="flex flex-col min-w-0 flex-1">
        <span class="text-sm font-semibold text-ink truncate" title="${member.name}">${member.is_me ? `You (${first(member.name)})` : member.name}</span>
        <span class="code text-xs truncate">${member.tracking_id}</span>
      </div>
    </div>
    <div class="flex flex-col gap-0.5 min-w-0">
      <span class="text-xs faint">Gives up</span>
      <span class="text-sm text-ink break-words"><span class="font-mono font-medium">${member.gives_room.number}</span> <span class="muted">${member.gives_room.hostel.name}</span></span>
      <span class="text-xs faint break-words">${roomDetails(member.gives_room)}</span>
    </div>
    <div class="flex flex-wrap items-center justify-between gap-2 pt-3 border-t border-line min-w-0">
      <p class="flex items-start gap-1.5 text-xs muted min-w-0">
        <span class="material-symbols-outlined text-[16px] text-ink-3 shrink-0" aria-hidden="true">arrow_forward</span>
        <span class="min-w-0 break-words">${member.is_me ? "You move into" : "Moves into"} <span class="font-mono text-ink">${next.gives_room.number}</span> <span class="faint">(${owner})</span></span>
      </p>
      ${raw(responseChip(member.response))}
    </div>
  </article>`;
}

// Connector between stacked cards on narrow screens.
function stackLink(text) {
  return html`
  <div class="lg:hidden flex items-center gap-2 pl-7 py-1 text-xs faint" aria-hidden="true">
    <span class="material-symbols-outlined text-[18px] text-ink-3">arrow_downward</span>${text}
  </div>`;
}

// Card centres stay this far (px) from the top and bottom of the canvas, so
// the cards (about 190px tall) never spill over its edge.
const EDGE_Y = 128;

// Where each card sits, as percentages of the canvas: around an ellipse,
// starting top left and going clockwise, stretched to fill the canvas.
function positions(n, height) {
  if (n === 2) return [{ x: 20, y: 50 }, { x: 80, y: 50 }];
  const start = -90 - 180 / n;
  const raw = Array.from({ length: n }, (_, i) => {
    const a = ((start + (360 / n) * i) * Math.PI) / 180;
    return { c: Math.cos(a), s: Math.sin(a) };
  });
  const span = (key) => [Math.min(...raw.map((p) => p[key])), Math.max(...raw.map((p) => p[key]))];
  const [c0, c1] = span("c"), [s0, s1] = span("s");
  const top = (EDGE_Y / height) * 100, bottom = 100 - top;
  return raw.map((p) => ({
    x: 18 + ((p.c - c0) / (c1 - c0 || 1)) * 64,
    y: top + ((p.s - s0) / (s1 - s0 || 1)) * (bottom - top),
  }));
}

export function canvasHeight(n) {
  if (n === 2) return 380;
  if (n === 3) return 560;
  if (n === 4) return 620;
  return 620 + (n - 4) * 160;
}

const reducedMotion = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

// Quadratic curve point.
const qpt = (a, c, b, t) => ({
  x: (1 - t) * (1 - t) * a.x + 2 * (1 - t) * t * c.x + t * t * b.x,
  y: (1 - t) * (1 - t) * a.y + 2 * (1 - t) * t * c.y + t * t * b.y,
});
const inside = (p, r, pad) => p.x > r.left - pad && p.x < r.right + pad && p.y > r.top - pad && p.y < r.bottom + pad;

// One arrow from card A to card B: a gentle curve bowed away from the ring's
// centre, trimmed so it starts and ends just outside the two cards.
function arrow(ra, rb, centre, n, index) {
  const a = { x: (ra.left + ra.right) / 2, y: (ra.top + ra.bottom) / 2 };
  const b = { x: (rb.left + rb.right) / 2, y: (rb.top + rb.bottom) / 2 };
  const mid = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
  let dx = mid.x - centre.x, dy = mid.y - centre.y;
  let len = Math.hypot(dx, dy);
  if (len < 1) { dx = 0; dy = index === 0 ? -1 : 1; len = 1; } // two members: one bows up, one down
  const bulge = n === 2 ? 110 : 60;
  const c = { x: mid.x + (dx / len) * bulge, y: mid.y + (dy / len) * bulge };
  const steps = 120;
  let t0 = 0, t1 = 1;
  for (let i = 0; i <= steps; i += 1) { if (!inside(qpt(a, c, b, i / steps), ra, 8)) { t0 = i / steps; break; } }
  for (let i = steps; i >= 0; i -= 1) { if (!inside(qpt(a, c, b, i / steps), rb, 10)) { t1 = i / steps; break; } }
  if (t1 <= t0) return null;
  const pts = [];
  for (let i = 0; i <= 40; i += 1) pts.push(qpt(a, c, b, t0 + ((t1 - t0) * i) / 40));
  const end = pts[pts.length - 1], before = pts[pts.length - 3];
  const ang = Math.atan2(end.y - before.y, end.x - before.x);
  const head = (da, d) => `${(end.x - d * Math.cos(ang + da)).toFixed(1)},${(end.y - d * Math.sin(ang + da)).toFixed(1)}`;
  return {
    d: `M ${pts.map((p) => `${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" L ")}`,
    head: `${end.x.toFixed(1)},${end.y.toFixed(1)} ${head(0.45, 11)} ${head(-0.45, 11)}`,
  };
}

const observers = new WeakMap();

// Fills the canvas with the member cards, then draws the arrows between them
// (only when the loop layout is showing; redrawn when the width changes).
export function renderRing(canvas, cycle) {
  const members = ordered(cycle);
  const n = members.length;
  let height = canvasHeight(n);
  const points = positions(n, height);
  canvas.style.setProperty("--ring-h", `${height}px`);
  canvas.innerHTML = html`
    <svg class="ring-arrows absolute inset-0 w-full h-full pointer-events-none hidden lg:block" aria-hidden="true"></svg>
    <ol class="relative flex flex-col lg:block lg:h-[var(--ring-h)]" aria-label="Who moves where, in order">
      ${members.map((m, i) => {
        const next = members[(i + 1) % n];
        const link = i < n - 1 ? stackLink(`${m.is_me ? "You move" : `${first(m.name)} moves`} into ${first(next.name)}'s room`) : "";
        return raw(html`<li class="lg:absolute lg:left-[var(--x)] lg:top-[var(--y)] lg:-translate-x-1/2 lg:-translate-y-1/2" style="--x:${points[i].x.toFixed(2)}%;--y:${points[i].y.toFixed(2)}%">${raw(memberCard(m, next))}${raw(link)}</li>`);
      })}
    </ol>
    <p class="lg:hidden flex items-center gap-2 pl-7 pt-1 text-xs faint">
      <span class="material-symbols-outlined text-[18px] text-ink-3" aria-hidden="true">u_turn_left</span>
      ${members[n - 1].is_me ? "You move" : `${first(members[n - 1].name)} moves`} into ${members[0].is_me ? "your" : `${first(members[0].name)}'s`} room, which closes the chain
    </p>`;

  let animated = false;
  const draw = () => {
    const svg = canvas.querySelector(".ring-arrows");
    if (!svg || getComputedStyle(svg).display === "none") return;
    const box = canvas.getBoundingClientRect();
    const rects = [...canvas.querySelectorAll(".ring-card")].map((el) => {
      const r = el.getBoundingClientRect();
      return { left: r.left - box.left, right: r.right - box.left, top: r.top - box.top, bottom: r.bottom - box.top };
    });
    // Two neighbours too close for a visible arrow: make the loop taller and try again.
    const crowded = rects.some((a, i) => {
      const b = rects[(i + 1) % n];
      return Math.max(b.left - a.right, a.left - b.right, b.top - a.bottom, a.top - b.bottom) < 40;
    });
    if (crowded && n > 2 && height < 2400) {
      height += 80;
      canvas.style.setProperty("--ring-h", `${height}px`);
      positions(n, height).forEach((p, i) => canvas.querySelectorAll("ol > li")[i]?.style.setProperty("--y", `${p.y.toFixed(2)}%`));
      requestAnimationFrame(draw);
      return;
    }
    const centre = { x: box.width / 2, y: box.height / 2 };
    svg.setAttribute("viewBox", `0 0 ${box.width.toFixed(0)} ${box.height.toFixed(0)}`);
    const arrows = rects.map((r, i) => arrow(r, rects[(i + 1) % n], centre, n, i)).filter(Boolean);
    svg.innerHTML = arrows.map((a) => `
      <path class="ring-line" d="${a.d}" fill="none" stroke="#3D4F66" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      <polygon class="ring-head" points="${a.head}" fill="#3D4F66" stroke="#3D4F66" stroke-width="1.5" stroke-linejoin="round"/>`).join("");
    if (!animated && !reducedMotion() && svg.animate) {
      for (const path of svg.querySelectorAll(".ring-line")) {
        const len = path.getTotalLength();
        path.style.strokeDasharray = `${len}`;
        path.animate([{ strokeDashoffset: len }, { strokeDashoffset: 0 }], { duration: 700, easing: "ease-out", fill: "both" })
          .finished.then(() => { path.style.strokeDasharray = ""; }).catch(() => {});
      }
      for (const head of svg.querySelectorAll(".ring-head")) {
        head.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 200, delay: 600, fill: "backwards" });
      }
    }
    animated = true;
  };

  observers.get(canvas)?.disconnect();
  if (window.ResizeObserver) {
    const ro = new ResizeObserver(() => draw());
    ro.observe(canvas);
    observers.set(canvas, ro);
  }
  requestAnimationFrame(draw);
}

// Compact "who has answered" row above the ring.
export function renderSteps(el, cycle) {
  el.innerHTML = ordered(cycle).map((m) => html`
    <li class="flex items-center gap-2 min-w-0 max-w-full">
      <span class="text-sm ${raw(m.is_me ? "text-ink font-semibold" : "muted")} truncate">${m.is_me ? "You" : m.name}</span>
      ${raw(responseChip(m.response))}
    </li>`).join("");
}

export function renderMatrix(head, body, cycle) {
  const cols = ordered(cycle);
  head.innerHTML = html`<tr>
    <th scope="col">Room detail</th>
    ${cols.map((m) => raw(html`<th scope="col" class="${raw(m.is_me ? "text-brass" : "")} whitespace-nowrap"><span class="font-mono">${m.gives_room.number}</span> ${m.is_me ? "(you give up)" : `(${first(m.name)})`}</th>`))}
  </tr>`;
  const rows = [
    ["Hostel and block", (r) => `${r.hostel.name}, block ${r.block}`],
    ["Floor", (r) => floorText(r.floor)],
    ["Beds", (r) => (r.seater === 1 ? "Single" : r.seater === 2 ? "Double sharing" : `${r.seater} sharing`)],
    ["Cooling", (r) => (r.ac ? "AC" : "Non-AC")],
    ["Washroom", (r) => (r.washroom === "attached" ? "Attached" : "Common")],
    ["Nearby", (r) => r.tags.join(", ") || "None listed"],
  ];
  body.innerHTML = rows.map(([label, value]) => html`<tr class="table-row">
    <th scope="row" class="py-3 px-4 text-left font-medium text-ink-2 whitespace-nowrap">${label}</th>
    ${cols.map((m) => raw(html`<td class="text-ink min-w-[10rem]">${value(m.gives_room)}</td>`))}
  </tr>`).join("");
}
