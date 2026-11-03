# Frontend

Five pages. They are plain HTML files with small JavaScript modules: no framework, no build
step except the CSS.

All pages share one calm, dark look (the rules are in `code/frontend/DESIGN-BRIEF.md`). The
pages describe what users can do; the server checks every rule again, so the pages are a
convenience, not the protection. There are no automated browser tests for the pages (see
[Testing](testing.md)).

| Page | File | Who | What they can do there |
|---|---|---|---|
| Sign in | `public/index.html` + `js/login.js` | everyone | Pick the Student, Hostel staff or Faculty tab and sign in with a `@thapar.edu` email; demo-account buttons fill in a demo login; live pool numbers |
| Find rooms | `public/rooms.html` + `js/rooms.js` | students | Filter rooms, build a ranked list of up to 5 choices, submit (feature 1). Choices can be exact rooms or "any room like this" (a hostel plus beds, AC or floor) |
| My swap (student dashboard) | `public/dashboard.html` + `js/dashboard.js` + `js/ring.js` | students | See the request's status, the swap chain picture, confirm or decline, withdraw |
| Lecture slots (faculty) | `public/slots.html` + `js/slots.js` | faculty | See your lectures and the week's timetable, offer one lecture, rank up to 5 slots that don't clash with your other lectures, confirm or decline a slot swap |
| Hostel staff | `public/admin.html` + `js/admin.js` | hostel staff | Two views. **Room swaps:** run TTC, compare with 1:1, approve swaps (feature 2), download the requests CSV, the event log and each approved swap's PDF approval form, switch automatic rounds on or off. **Lecture slots:** run slot rounds and approve slot swaps. Below both views: the email outbox |

After signing in, each kind of account lands on its own page: students on the dashboard,
faculty on `slots.html`, hostel staff on `admin.html` (`homeFor` in `js/api.js`).

Shared modules: `js/api.js` (talks to the server), `js/ui.js` (escaping, toasts, dates),
`js/nav.js` (fills the top bar with the signed-in user).

## What changed from the reference designs, and why

The first version of each page started from one of the team's reference designs. Content
that was fake, or wrong for this project, was replaced with real data or given a real job:

| In the reference | In CampusSwap | Why |
|---|---|---|
| "Gale-Shapley", "Deferred Acceptance", "Edmonds-Karp" | Top Trading Cycles | Those are different algorithms; the proposal uses TTC |
| Invented numbers (1,420 peers, 98% confidence, 99% match, ping) | Real counts from the database | An examiner can check them |
| Shibboleth, Duo 2FA, "cryptographic escrow", Redis | Hashed passwords and session cookies | Those don't exist in our system |
| US universities, `.edu` check | Thapar, `@thapar.edu` check (also enforced by the server) | Our users |
| Hard-coded 3-person swap ring | Ring drawn for any chain length (`ring.js`) | Real chains are 2, 3, 4… students |
| Timer-driven fake terminal log | The engine's real round-by-round trace | Shows how TTC actually decided |
| "Simulation mode" / constraint sliders | Dry run and TTC-vs-1:1 comparison | Matches the proposal's evaluation plan |
| Photos from Google image servers | Initials avatars | Links could break; no real photos of students |

## Styling

Every page has its own Tailwind config in `code/frontend/tailwind/`, and all of them share
one set of colour names from `tailwind/theme.cjs`, so the pages look alike. Shared classes
(buttons, cards, fields, chips, the top bar) are in `src/tailwind.css`. `npm run build`
turns these into one CSS file per page in `public/assets/`, and copies the fonts into
`public/fonts/`. Both are committed, so the app works with no internet and without Node.

## Safety: never trust text from the server

Names and room labels come from the database. If they were put into the page as raw HTML,
a name like `<img onerror=...>` could run code in someone else's browser (*cross-site
scripting*). Every page builds HTML with the `html` helper in `ui.js`, which escapes each
inserted value. Only our own fixed markup is inserted unescaped, through `raw()`.

## States every page must handle

- **Loading:** placeholder blocks (`.skeleton`) until data arrives.
- **Empty:** e.g. "No request yet", "No rooms match these filters", "No round yet".
- **Error:** a toast with the server's message, or an inline box with *Try again*.
- **Long text:** names and room labels are cut off with `truncate`, and the full text shows on hover.
- **Small screens:** layouts stack on phones; the swap ring becomes a list of cards; the
  ranked list has ↑/↓ buttons because drag-and-drop doesn't work on touch screens.

## Who may see which page

Each page asks the server who is signed in (`requireUser` in `api.js`). Not signed in →
back to the sign-in page. Someone opening another role's page is sent to their own page,
and the server also refuses calls from the wrong kind of account (403), so hiding a page
is not the only protection.
