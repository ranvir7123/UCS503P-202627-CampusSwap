# Showcase guide (A to Z)

Everything you need to show CampusSwap to ma'am: what exists, how to start it, what to
click, what to say, and what to do if something goes wrong. Read it once fully before
the lab. The steps are numbered; do them in order.

---

## 1. The two links (this confuses people, so read carefully)

| What | Link | Where it works | Needs internet? |
|---|---|---|---|
| **The app** (login, rooms, dashboard, admin) | <http://127.0.0.1:8000> | **Only on the laptop running the server** | No |
| **The documentation website** (docs, diagrams, study guide) | <https://ranvir7123.github.io/UCS503P-202627-CampusSwap/> | Any device, anywhere | Yes |
| **The code on GitHub** | <https://github.com/ranvir7123/UCS503P-202627-CampusSwap> | Anywhere | Yes |
| **Automatic test results (CI)** | <https://github.com/ranvir7123/UCS503P-202627-CampusSwap/actions> | Anywhere | Yes |

**Why isn't the app on GitHub Pages?** GitHub Pages can only host fixed files (pages,
pictures). The app needs a Python server and a database running all the time, so it runs
on a laptop. If ma'am asks: *"The documentation is published on GitHub Pages. The app runs
on a local server because it needs Python and a database; putting it on a cloud server is
future work."*

`127.0.0.1` means "this computer". That's why the app link only works on the laptop where
you started it.

---

## 2. What exists (the full list)

| Thing | Where |
|---|---|
| Working app: 4 pages (login, explore rooms, student dashboard, admin) | `code/frontend/public/` |
| Server and all rules | `code/backend/app/` |
| The matching algorithm (Top Trading Cycles) | `code/backend/engine/` |
| Demo data (4 hostels, 72 rooms, 144 students, 1 warden) | `code/backend/seed.py` |
| 89 automated tests | `code/backend/tests/` |
| 4 UML diagrams: pictures | `docs/diagrams/*.png` and `*.svg` |
| 4 UML diagrams: source text | `diagrams/*.puml` |
| Diagrams with explanations | Docs site → **Diagrams** |
| Documentation website | `docs/` (published to GitHub Pages) |
| Study guide for P1–P4 + 35 viva questions | Docs site → **Study guide** |
| All demo logins | Docs site → **Demo accounts** |
| Design spec and build plans | `planning/` |
| Weekly journals (one folder each) | `journals/` |
| Project proposal | `project-proposal/` |
| Prototype report (LaTeX) | `project-report-prototype-stage/` (**not written yet**: needs the Overleaf template) |

---

## 3. Set up a laptop (only once per laptop)

Skip this on Ranvir's laptop: it's already set up in `C:\dev\Swe-Project`.

1. **Install Python 3.12** from <https://www.python.org/downloads/>. On the first installer
   screen, tick **"Add python.exe to PATH"**.
2. **Install Git** from <https://git-scm.com/download/win> (keep all default options).
3. Open **PowerShell** (Start menu → type *PowerShell*) and run these one by one:

    ```powershell
    cd $HOME\Desktop
    git clone https://github.com/ranvir7123/UCS503P-202627-CampusSwap.git
    cd UCS503P-202627-CampusSwap
    python -m venv .venv
    .venv\Scripts\python -m pip install -r code/backend/requirements-dev.txt
    ```

    The last command downloads the libraries and needs internet (about 1 minute).

You don't need Node.js unless you change the page styling.

---

## 4. Start the app (every time)

1. Open **PowerShell** in the project folder:

    ```powershell
    cd C:\dev\Swe-Project
    ```

    (On other laptops, use the folder you cloned into, e.g. `cd $HOME\Desktop\UCS503P-202627-CampusSwap`.)

2. Start the server:

    ```powershell
    .venv\Scripts\python code/backend/run.py
    ```

3. Wait for the line **`CampusSwap running at http://127.0.0.1:8000`**.
4. Open **<http://127.0.0.1:8000>** in Chrome or Edge.
5. **Keep the PowerShell window open.** Closing it stops the app.

**To stop the app:** click the PowerShell window and press `Ctrl + C`.

---

## 5. Reset the data (fresh start)

Use this **before the demo** and whenever the data gets messy. It deletes everything that
happened (requests, rounds, swaps, logins) and loads the original demo data again.

1. Stop the app (`Ctrl + C` in its PowerShell window).
2. Start it again with `--reset`:

    ```powershell
    .venv\Scripts\python code/backend/run.py --reset
    ```

3. You'll see `Loaded demo data into campusswap.db`. Everyone is signed out; sign in again.

After a reset: 12 open requests, no matching round yet, and student1, student2, student3
have no request.

---

## 6. Accounts

**The password for every account is `campus123`.**

| Email | Tab to use | Who |
|---|---|---|
| `warden@thapar.edu` | Hostel Staff | The warden (admin) |
| `student1@thapar.edu` | Student | Lives in Hostel M, room A-101 |
| `student2@thapar.edu` | Student | Lives in Hostel M, room B-101 |
| `student3@thapar.edu` | Student | Lives in Hostel M, room A-201 |
| `stu001@thapar.edu` … `stu144@thapar.edu` | Student | Every other student (see **Demo accounts** on the docs site). Three numbers in Hostel M are skipped because student1–3 use those beds. |

- **Quick login:** on the login page, click **Use student demo** (fills in student1) or
  **Use hostel staff demo** (fills in the warden), then **Sign in**.
- **Sign out:** the **logout icon** at the top right of every page.
- **Women's hostels:** K and N (accounts `stu073` to `stu144`). For example,
  `stu074@thapar.edu` lives in Hostel K and has no request yet. She only sees K and N
  rooms. That's a good way to show the gender rule.
- **Being two people at once:** each browser window shares one login. To be the warden
  *and* a student at the same time, use a normal window for one and an **Incognito /
  InPrivate window** (`Ctrl + Shift + N` in Chrome, `Ctrl + Shift + P` in Edge) for the
  other. A different browser also works.

**New accounts:** there is no sign-up page. That's on purpose: at the university, accounts
would come from the institute login. With 145 ready-made accounts you shouldn't need a new
one. If you do, see section 12.

---

## 7. The demo script (about 8 minutes)

### Before ma'am arrives (5 minutes)

1. Reset the data (section 5) and leave the app running.
2. Open these tabs:
    - **Tab 1:** the docs site home page (for the intro and the diagrams).
    - **Tab 2 (normal window):** <http://127.0.0.1:8000>, which you'll sign in as the warden.
    - **Tab 3 (Incognito window):** <http://127.0.0.1:8000>, which you'll sign in as students.
3. To save time, **submit student2 and student3's requests now**. In the Incognito window:
    - Sign in as `student2@thapar.edu` → **Explore Rooms** → set the hostel filter to
      **Hostel M** → type `A-201` in the search box → **Rank in Preferences** →
      **Lock 1 Preference & Submit**. Then sign out.
    - Sign in as `student3@thapar.edu` → same steps, but search `A-101`. Sign out.
4. Optionally, in a PowerShell window, run the tests once so the result is on screen:

    ```powershell
    .venv\Scripts\python -m pytest
    ```

    It should end with **`89 passed`**.

### Step 1: the pitch (30 seconds, docs site home page)

Say: *"Hostel rooms are fixed for the semester. To move, you need someone who wants your
room and has one you want, so most swaps never happen. CampusSwap collects everyone's
ranked choices and uses the Top Trading Cycles algorithm to find chains of swaps, like
A → B → C → A, where everyone gets a room they prefer. Students confirm, the warden
approves, and the rooms change."*

### Step 2: the login page (1 minute, Tab 3)

- Point out the **Student / Hostel Staff** switch and the **@thapar.edu** check (type
  something wrong to show the red "@thapar.edu required" badge).
- The numbers on the page (open requests, rooms) are **live from the server**.
- Say: *"Passwords are stored hashed, and the login cookie can't be read by page scripts."*
- Click **Use student demo** → **Sign in** (this is student1).

### Step 3: feature 1, submit a ranked request (1.5 minutes, as student1)

1. On the dashboard, show **"Start your room exchange"**, the current room card
   (A-101) and the 5 steps on the right.
2. Click **Choose rooms to swap into** (or **Explore Rooms**).
3. Show the filters, the room cards, the **"open to swap"** badges and the ranked list on the right.
4. Hostel filter → **Hostel M**, search `B-101` → **Rank in Preferences**.
5. Click **Lock 1 Preference & Submit**. You get a tracking ID (**CS-2026-0015** if you did
   the preparation steps above) and land on the dashboard showing **"In the matching pool"**.
6. Say: *"The server checks every rule: at most 5 rooms, no duplicates, not your own room,
   only hostels you're allowed in, one active request at a time."*

### Step 4: feature 2, run the matching round (2 minutes, Tab 2)

1. Sign in with **Use hostel staff demo** → **Sign in**. You're on the **Admin Engine Room**.
2. Show the cards: **15 students in the pool**, no round yet.
3. Click **Compare on the current pool** (the right-hand card at the bottom). It shows
   **TTC 80% vs 1:1 swaps only 13.3%**. Say: *"This is the evaluation from our proposal:
   same students, and multi-way chains match far more people. Nothing is saved; it's a dry run."*
4. Click **Run TTC Matching Round** → **OK** in the pop-up.
5. The black **Engine trace** box shows what TTC did, round by round: *"Round 1: 15 students
   point at the owner of their best available room"* and the chains it found. Read one chain aloud.
6. The cards now show **1 two-way swap**, **3 multi-way loops** and **Match Yield 80%**
   (target ≥ 60%). In the table, click any row to expand its ranked choices and chain members.

### Step 5: confirm the swap (1.5 minutes, Tab 3)

1. Refresh student1's dashboard. It now shows **"We found you a swap"**, the **3-way swap
   ring** picture (you, your new room's owner, the third member) and a **48-hour countdown**.
2. Click the **Compare rooms** tab to show the room details side by side.
3. Click **Confirm swap**.
4. Sign out, sign in as **student2**, click **Confirm swap**. Do the same for **student3**.
   The last one sees **"Everyone has confirmed"**.
5. Say: *"If anyone declines, or someone doesn't answer within 48 hours, the chain is
   cancelled and the others go back into the pool."*

### Step 6: approve (30 seconds, Tab 2)

1. Refresh the admin page. The banner says **"1 swap ready to approve"**; click it.
2. Click **Approve swap** → **OK**.
3. In Tab 3, sign in as student1: the room card now says **Room B-101**, and all 5 steps are done.

### Step 7: the proof (1 minute)

- **Diagrams:** docs site → **Diagrams** (Use Case, Class, Sequence, Activity, each with the
  reasons for its relationships).
- **Tests:** the PowerShell window with **89 passed**, and the GitHub **Actions** page with green ticks.
- **Code:** show the folders on GitHub: `code/backend/engine` (the algorithm),
  `code/backend/app` (server), `code/frontend` (pages).
- **API page:** <http://127.0.0.1:8000/docs> lists every endpoint (this page needs internet).

### Optional extras (if she asks)

- **Decline:** after a round, sign in as `stu001@thapar.edu` (in the demo 2-way swap) and
  click **Decline swap**. The chain is cancelled and the partner goes back to the pool.
- **Gender rule:** sign in as `stu074@thapar.edu`. Only Hostels K and N appear.
- **Dry run:** admin → **Dry run: OFF** button turns it ON. Then Run shows the result
  without saving anything.
- **Export CSV:** admin → **Export CSV** downloads every request as a spreadsheet.

---

## 8. The diagrams: where they are and what to say

| Diagram | Picture file | What it shows (one line) |
|---|---|---|
| Use Case | `docs/diagrams/use-case.png` | Who (student, warden) can do what; «include» = always happens, «extend» = optional |
| Class | `docs/diagrams/class.png` | The tables and classes and how they link (Student *is a* User, a Room *has* Seats) |
| Sequence | `docs/diagrams/sequence.png` | One swap from request to approval, message by message |
| Activity | `docs/diagrams/activity.png` | The life of a request, including the decline and deadline branches |

- **To show them:** docs site → **Diagrams** (big, with explanations), or open the PNG files.
- **For the report:** use the PNG files from `docs/diagrams/`.
- **To change one:** edit its `diagrams/*.puml` file, then run
  `.venv\Scripts\python diagrams/render.py` (needs internet).

The justification for every relationship is on the Diagrams page. Read it before the lab.

---

## 9. Show it on a phone (optional, may not work on college Wi-Fi)

1. Start the app so other devices can reach it:

    ```powershell
    .venv\Scripts\python code/backend/run.py --host 0.0.0.0
    ```

2. If Windows asks, click **Allow access** (private networks).
3. Find the laptop's address: run `ipconfig` and copy the **IPv4 Address** (e.g. `192.168.1.5`).
4. On a phone **on the same Wi-Fi**, open `http://192.168.1.5:8000`.

College Wi-Fi often blocks this. If it doesn't load in 10 seconds, skip it and use the
browser's phone view instead: press `F12` → click the phone icon (**Toggle device toolbar**).

---

## 10. If something goes wrong

| What you see | What to do |
|---|---|
| Browser says **"This site can't be reached"** at 127.0.0.1:8000 | The app isn't running. Start it (section 4). |
| A page says **"Can't reach the CampusSwap server"** | Same: the server stopped. Start it and refresh. |
| **`address already in use`** when starting | The app is already running in another window. Use that one, or start on another port: `run.py --port 8001` and open `http://127.0.0.1:8001`. |
| **`python` is not recognized** | Python isn't installed or wasn't added to PATH. Reinstall and tick "Add to PATH". |
| **`No module named ...`** | You skipped the install step, or aren't in the project folder. Do section 3, step 3. |
| **"Wrong email or password"** | The password is `campus123`. If you reset while logged in, sign in again. |
| **"This account belongs on the Hostel Staff tab"** | You used the wrong tab; the page switches it for you. Click Sign in again. |
| **"You already have an active request"** | That student already submitted. Use another student, or reset (section 5). |
| Admin shows no chain for your 3 students | Check all three submitted the right rooms (student1 → B-101, student2 → A-201, student3 → A-101) *before* running the round. Otherwise reset and redo. |
| Page looks unstyled (plain text) | Press `Ctrl + F5`. If still broken, the CSS files are missing: `git pull` again. |
| Everything is messy | Reset (section 5). It takes 5 seconds. |

---

## 11. Honest answers to tricky questions

- **"Is it deployed?"** The docs are live on GitHub Pages; the app runs locally (see section 1).
- **"Is this real student data?"** No, it's all made up. Real data needs university permission.
- **"Is this Thapar's real login?"** No, it's email + password. Institute single sign-on is future work.
- **"What's not done?"** Notifications, the PDF approval form, the faculty slot module, a
  background timer for deadlines, and a cloud deployment. See **Limitations and Phase 2**.
- **"Who did what?"** Each of you should say your P-role (see the **Study guide**).

---

## 12. Advanced (only if needed)

- **Get the latest code** on a teammate's laptop:

    ```powershell
    git pull
    ```

- **Run on another port:** `.venv\Scripts\python code/backend/run.py --port 8001`.
- **Where the data lives:** `code/backend/campusswap.db` (one file). Deleting it is the same as `--reset`.
- **Adding a brand-new account:** not possible from the app (no sign-up page). Either use
  one of the 145 demo accounts, or add a person to `code/backend/seed.py` and run with
  `--reset`. Ask Ranvir before editing the seed file: the demo numbers (75% / 80%) depend on it.

## 13. Command card (copy these)

```powershell
cd C:\dev\Swe-Project                                   # go to the project
.venv\Scripts\python code/backend/run.py                # start the app
.venv\Scripts\python code/backend/run.py --reset        # start fresh (wipes all changes)
.venv\Scripts\python -m pytest                          # run all 89 tests
.venv\Scripts\python diagrams/render.py                 # re-draw the diagrams
```

Stop the app: `Ctrl + C`. App: <http://127.0.0.1:8000>. Docs: <https://ranvir7123.github.io/UCS503P-202627-CampusSwap/>.
Password for every account: `campus123`.
