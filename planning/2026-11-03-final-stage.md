# Final stage: finish every Planned requirement, better screens, final report

Spec: `srs/main.tex` (every row tagged `\Planned`). Date: 2026-11-03.

## Who uses this and what they need

- **Student** (hostel resident): wants a better room without hunting for a
  swap partner. Today they must name exact rooms; often they only care about
  "any single AC room". They miss the 48-hour confirm window because nothing
  tells them outside the site.
- **Hostel office / warden**: runs rounds, approves swaps, keeps records. Today
  they must remember to press "Run", have no paper form to file, and cannot
  export the history for an audit.
- **Faculty member**: owns a lecture slot that suits them badly and would take
  another one. Nothing exists for them yet, though the project title promises
  slot coordination.
- **Anyone attacking the sign-in page**: today can guess passwords forever and
  sign in with a non-institute address if they skip the page's own check.

## Tasks (each: failing test first, then code, then full suite)

1. **Institute email on the server** (FR-AUTH-09). `POST /api/auth/login` with
   an address not ending in `@thapar.edu` → 400 `not_institute_email`.
2. **Sign-in limit** (FR-AUTH-10, NFR-SEC-08). Table `login_failures`
   (key, created_at). 5 failures for one email, or 20 from one IP, within 15
   minutes → 429 `too_many_attempts` (checked before the password). A
   successful sign-in clears that email's failures.
3. **HTTPS + Secure cookie** (NFR-SEC-07). `create_app(secure=...)`, default
   from env `CAMPUSSWAP_SECURE=1`. When on: cookie `Secure`, HTTP → HTTPS
   redirect, `Strict-Transport-Security` header. `run.py --https --cert --key`
   passes the files to uvicorn. Off by default for local http demo.
4. **Room-type choices** (FR-ROOM-07). A preference is either one room or a
   type: hostel + optional seater, AC, floor. Request body
   `choices: [{room_id} | {type: {...}}]` (old `room_ids` still accepted).
   A type expands to the matching rooms (not the student's own) in room order;
   the received rank is the first choice that matches. A type matching no
   other room → 400 `empty_type`.
5. **Event log download** (FR-TRACK-08). `GET /api/admin/events.csv`.
6. **Email notices** (FR-CONF-06). Table `emails` (outbox). On a saved match
   each member gets "match found"; a pending member gets one reminder when 12
   hours or less remain. Delivery via SMTP when `CAMPUSSWAP_SMTP_HOST` is set,
   otherwise mail stays queued and the staff page shows it truthfully as
   "not sent: no mail server set up". `GET /api/admin/emails`.
7. **Scheduled rounds** (FR-MATCH-10). Table `schedule` (one row): enabled,
   every_hours, next_run_at, set_by. `GET/PUT /api/admin/schedule`.
   `tick(db, now)` = expire overdue, reminders, due round, deliver mail; a
   background loop calls it every 30 s (off in tests, which call `tick`).
8. **Approval form PDF** (FR-APPR-03). `SwapCycle.approved_by_id`.
   `GET /api/admin/cycles/{id}/approval.pdf` (approved cycles only, else 409
   `not_approved`): every member, rooms given/received, choice rank, when they
   confirmed, who approved and when, signature lines. Library: fpdf2.
9. **Faculty slot exchange** (FR-SLOT-01). Role `faculty`; tables
   `lecture_slots`, `slot_requests`, `slot_preferences`, `slot_cycles`,
   `slot_cycle_members`. Faculty offer one slot and rank up to 5 others that
   do not clash with their other slots. Staff run a slot round (same TTC
   engine, dry run or saved), members accept/decline, staff approve and the
   slots change owner. New page `slots.html`; staff page gets a Slots tab.
10. **Better screens.** Every page checked by screenshot (desktop + phone,
    empty / loading / error / long text). Calm colours, consistent spacing,
    dark mode works.
11. **Final report** in `project-report-final/` with `tietreport.cls`:
    requirements status, design, diagrams, screenshots, and test cases as
    tables (ID, requirement, steps, input, expected, actual, result) taken
    from the real test run.

## Global constraints

- Engine stays free of database and web code.
- Every UI claim stays truthful (no fake numbers, no fake "sent" mail).
- Existing tests keep passing; old `room_ids` request body keeps working.
- Schema changes need `run.py --reset`; `run.py` says so if the DB is stale.

## Not built (needs something we do not have)

- **FR-AUTH-11 Microsoft single sign-on**: needs an app registration in
  Thapar's Microsoft tenant (client id and secret) that only the institute's
  IT office can create. Without it the flow cannot be tested end to end.
