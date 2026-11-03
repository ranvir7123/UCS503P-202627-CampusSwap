# CampusSwap screens: shared design brief (final stage)

CampusSwap is Thapar Institute's (TIET) hostel room swap and lecture slot swap
system. Students (mostly on phones) rank rooms they would rather live in; a
matching engine (Top Trading Cycles) finds chains of students who can all swap;
everyone in a chain confirms; hostel staff approve. Faculty do the same with
weekly lecture slots. Hostel staff use laptops.

## The look: calm and dark, only dark

- Dark only. There is no light theme and no theme toggle. Never add `dark:` variants.
- Calm: this is a university office tool. No gradients, shimmer, pulsing/pinging
  dots, bouncing icons, floating badges, glow shadows, emoji, confetti.
  Motion only when it answers a user action (opening, expanding, a toast).
- Colours come ONLY from the tokens in `tailwind/theme.cjs`:
  `canvas sunken panel raised line line-strong ink ink-2 ink-3 brass brass-hover brass-ink info ok bad`
  (use opacity forms like `bg-ok/10`, `border-info/30`). No slate/rose/coral/amber/
  emerald/violet etc. Brass is the one accent: main button, focus, the current
  step. Status colours: open/in pool = info, waiting for answers = brass,
  confirmed/approved = ok, declined/cancelled/error = bad.
- Shared classes in `src/tailwind.css` (use them, read the file):
  `page-title section-title muted faint code card card-pad btn-primary
  btn-secondary btn-ghost btn-danger btn-sm icon-btn label field check
  chip-neutral chip-info chip-ok chip-warn chip-bad notice-info notice-ok
  notice-warn notice-bad topbar topbar-inner brand brand-mark nav-link avatar
  table-head table-row skeleton`.
- Type: Plus Jakarta Sans. Scale: 12 (small print) / 14 (body, default) / 16
  (section titles) / 24 (page title). Nothing below 12px (`text-xs`): no
  `text-[10px]`, `text-[11px]`. Sentence case everywhere. No ALL-CAPS labels,
  no `uppercase`, no `tracking-wider` labels. Monospace (`font-mono` / `.code`)
  only for real codes: tracking IDs like CS-2026-0004, room numbers, times in the trace.
- Spacing on a 4px grid; cards `rounded-xl`, buttons/inputs `rounded-lg`, chips
  `rounded-md`. Content width `max-w-6xl mx-auto px-4 sm:px-6`. Left aligned.
- Icons: Material Symbols Outlined (already self-hosted:
  `<span class="material-symbols-outlined text-[18px]">name</span>`), sparingly,
  `aria-hidden="true"` when decorative.
- Plain words for a student audience. Buttons say exactly what happens
  ("Send request", "Confirm swap"). Errors say what went wrong and what to do.
  Never show a number or claim that is not real data from the server.

## Every page

- `<body>` gets no colour classes (base styles set them). Put
  `<link rel="stylesheet" href="/assets/<page>.css"/>` in head. Remove the old
  inline `<style>` animations that the new design no longer uses.
- Shared top bar (same on every signed-in page):

```html
<header class="topbar"><div class="topbar-inner">
  <a class="brand" href="/"><span class="brand-mark"><span class="material-symbols-outlined text-[18px]" aria-hidden="true">sync_alt</span></span>CampusSwap</a>
  <nav class="hidden sm:flex items-center gap-1" aria-label="Pages"> ...nav-link items, aria-current="page" on this one... </nav>
  <div class="ml-auto flex items-center gap-3">
    <div class="avatar" data-user-initials></div>
    <div class="hidden md:flex flex-col leading-tight"><span class="text-sm font-semibold" data-user-name>…</span><span class="text-xs faint" data-user-sub></span></div>
    <button class="icon-btn" data-logout type="button" aria-label="Sign out" title="Sign out"><span class="material-symbols-outlined text-[20px]" aria-hidden="true">logout</span></button>
  </div>
</div></header>
```
  `fillHeader(me)` from `public/js/nav.js` fills it.
- States you must handle and make look right: loading (skeleton blocks the same
  size as the content), empty (say what it means and what to do next, with the
  action button), error (notice-bad with the server's message and a "Try again"
  button), very long text (names, room labels, emails: `truncate` or
  `break-words`, never overflow), phone width 375px (no sideways scrolling of
  the page; wide tables scroll inside their own `overflow-x-auto` box).
- Accessibility: real `<button type="button">`, labels tied to inputs,
  `aria-live="polite"` on areas that update, visible keyboard focus (base style
  does it; don't remove outlines), contrast stays with the tokens.
- Escape every server value: use `html\`\`` / `esc()` from `public/js/ui.js`.
- Toasts: `toast()` / `toastError()` from `ui.js`.

## Rules for you (the builder of one page)

- Only edit the files your task names. Do NOT edit `src/tailwind.css`,
  `tailwind/*.cjs`, `public/js/ui.js`, `api.js`, `nav.js`, other pages, or
  anything in `code/backend`. If you need a shared change, say so in your report.
- Keep every real feature the page has today (read the current HTML and JS fully
  first) unless the brief says to remove it. Keep the reference layout's
  structure (what is where); change the look.
- To see real server data shapes, read `code/backend/app/routers/*.py`,
  `code/backend/app/services/views.py` (and `slots.py`, `mail.py`,
  `schedule.py`) and the tests in `code/backend/tests/`. You can print real
  JSON with an in-memory server (safe, touches no files), run from
  `C:\dev\Swe-Project\.claude\worktrees\tiet-latex-report-template-7fad3e`:
  `.venv/Scripts/python -c "import sys; sys.path.insert(0,'code/backend'); ..."`
  using `from app.main import create_app; from seed import seed;
  from fastapi.testclient import TestClient` — `app=create_app('sqlite://')`,
  `with app.state.session_factory() as db: seed(db)`, then log in with
  `POST /api/auth/login {email, password: 'campus123', role}`.
  Do NOT run `run.py` and do not start servers on ports.
- Build only your page's CSS, from `code/frontend`:
  `node node_modules/tailwindcss/lib/cli.js -c tailwind/<page>.config.cjs -i src/tailwind.css -o public/assets/<page>.css --minify`
  It must finish with no errors. Then check: `node --input-type=module --check < public/js/<page>.js` (the scripts use `import`, so a plain `node --check` refuses them).
- Do not commit. Do not run git commands that change anything.
- Report back: files changed, every feature added or removed, anything you were
  unsure of, and any shared change you need. Keep it short.
