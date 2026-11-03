# Data model

All tables are defined in `code/backend/app/models.py` using SQLAlchemy. The database is a
single SQLite file, `code/backend/campusswap.db`. Times are stored in UTC.

## Tables

### People and sign-in

| Table | One row is… | Important columns |
|---|---|---|
| `users` | anyone who can sign in | `email` (unique), `name`, `password_hash`, `role` (`student` / `admin` / `faculty`); students also have `roll_no`, `gender`, `year`, `branch`; faculty have `department` |
| `login_sessions` | one signed-in browser | `token_hash` (SHA-256 of the cookie), `user_id`, `expires_at` |
| `login_failures` | one failed sign-in, kept for 15 minutes | `key` (which limit it counts towards: `email:...`, `ip:...` or `email_ip:...`), `created_at` |

### Rooms

| Table | One row is… | Important columns |
|---|---|---|
| `hostels` | a hostel | `code`, `name`, `gender` (who may live there), `warden_name` |
| `rooms` | a room | `hostel_id`, `block`, `floor`, `number`, `seater` (1–3 beds), `ac`, `washroom`, `tags` |
| `seats` | one bed in a room | `room_id`, `label` (A/B/C), `occupant_id` (**unique**: one student per bed) |
| `swap_requests` | a student asking to move | `tracking_id`, `student_id`, `seat_id` (the bed they offer), `status` |
| `preferences` | one ranked choice | `request_id`, `rank` (1–5), and **either** `room_id` (one exact room) **or** the room-type columns `type_hostel_id`, `type_seater`, `type_ac`, `type_floor` ("any room like this"; an empty filter means "any"); unique on (request, rank) and (request, room) |
| `match_runs` | one press of Run or Compare, or one automatic round (rooms and lecture slots) | `algorithm` (`ttc`, `pairwise` or `slot_ttc`), `dry_run`, `pool_size`, `matched`, `yield_pct`, `first_choice_pct`, `cycles_by_length`, `trace` |
| `swap_cycles` | one room chain found by a saved run | `match_run_id`, `status`, `deadline` (48 h after the run), `approved_by_id` |
| `cycle_members` | one student in a room chain | `cycle_id`, `request_id`, `position`, `gives_seat_id`, `receives_seat_id`, `received_rank`, `response`, `reminded_at` (when the reminder email was queued) |

### Lecture slots

| Table | One row is… | Important columns |
|---|---|---|
| `lecture_slots` | one weekly lecture | `day` (0 = Monday), `start_min` (minutes after midnight), `length_min` (50), `hall`, `course_code`, `course_name`, `owner_id` (the teacher) |
| `slot_requests` | a teacher asking to move one lecture | `tracking_id` (`SL-...`), `faculty_id`, `slot_id` (the slot offered), `status` |
| `slot_preferences` | one ranked slot | `request_id`, `rank` (1–5), `slot_id`; unique on (request, rank) and (request, slot) |
| `slot_cycles` | one slot chain found by a saved slot round | `match_run_id`, `status`, `deadline` (48 h), `approved_by_id` |
| `slot_cycle_members` | one teacher in a slot chain | `cycle_id`, `request_id`, `position`, `gives_slot_id`, `receives_slot_id`, `received_rank`, `response` |

### Staff tools

| Table | One row is… | Important columns |
|---|---|---|
| `events` | one line of the audit log | `kind`, `message`, `student_id` (the person it is about; also used for teachers), `cycle_id` |
| `emails` | one email in the outbox | `kind` (`match_found`, `deadline_reminder`, `slot_match_found`), `to_user_id`, `to_address`, `subject`, `body`, `status` (`queued` / `sent`), `attempts`, `error`, `sent_at` |
| `schedule` | the one automatic-round setting (a single row) | `enabled`, `every_hours`, `next_run_at`, `set_by_id`, `last_run_id` |

`Student`, `Admin` and `Faculty` share the `users` table (*single-table inheritance*: one
table, with a `role` column saying which kind each row is). In the class diagram `Student`
and `Admin` are drawn as two classes that inherit from `User`.

## Why seats and not just rooms?

A double room has two students in it. A swap moves one student, not the whole room. So a
student owns a **seat**, and a request offers that seat. Preferences are still for
**rooms**, because students choose rooms, not bed labels.

## How statuses change

### Swap request

| From | Event | To |
|---|---|---|
| — | student submits | `open` |
| `open` | student withdraws | `withdrawn` |
| `open` | a saved round puts it in a chain | `matched` |
| `matched` | the chain is dissolved and this student declined or didn't answer | `withdrawn` |
| `matched` | the chain is dissolved but this student had accepted (or someone else declined) | `open` (back in the pool) |
| `matched` | the warden approves the chain | `completed` |

A student can have only one request that is `open` or `matched` at a time. Lecture slot
requests follow the same statuses and the same rule, per teacher.

### Swap cycle

| From | Event | To |
|---|---|---|
| — | saved TTC round | `proposed` |
| `proposed` | every member accepts | `confirmed` |
| `proposed` | any member declines, or the deadline passes | `dissolved` |
| `confirmed` | the warden approves | `approved` (seats change hands) |

Lecture slot chains move through the same statuses. One extra case: if, at approval, a
teacher no longer teaches the slot they were giving (the timetable changed after everyone
confirmed), the chain becomes `dissolved` and everyone in it goes back to `open`.

### Cycle member response

`pending` → `accepted` or `declined`. Each member can answer once.

## Rules the database itself enforces

- One occupant per seat (`seats.occupant_id` is unique). That's why approval first empties
  every seat in the chain, then refills them.
- A request can't rank the same room twice or use the same rank twice (the same holds for
  slot requests and slots).
- **One active request per person.** A *partial unique index* (a uniqueness rule that only
  covers rows matching a condition) on `swap_requests.student_id` and on
  `slot_requests.faculty_id`, limited to rows whose status is `open` or `matched`. So even if
  two submits arrive at the same moment, the database lets only one through; the other gets
  `409 already_active`.
- Foreign keys are switched on for SQLite (`PRAGMA foreign_keys=ON` in `db.py`), so rows
  can't point at things that don't exist.

## Demo data

`code/backend/seed.py` builds 4 hostels (J and M for men, K and N for women), 72 rooms,
one student in every seat (144 students), the warden account, and 12 open requests arranged
into a known 2-way, 3-way and 4-way chain plus 3 students who can't be matched. It also adds
8 teachers with 2 lectures each (16 slots) and 4 open slot requests that give one 3-way
slot chain plus 1 teacher who can't be matched. All of it is made up.

## Old database files

`run.py` checks that every table and column the code expects is in `campusswap.db`
(`schema_is_current()`). If the file was made by an older version, it stops and asks you to
run again with `--reset`, which deletes the file and loads fresh demo data. There are no
migrations (scripts that upgrade an old database in place).
