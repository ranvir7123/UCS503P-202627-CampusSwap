# Matching engine: Top Trading Cycles

The engine lives in `code/backend/engine/`. It is plain Python: no database, no web code.
That keeps it easy to test and easy to explain.

## The problem in one picture

Every student in the pool **owns** a seat (a bed) and **wants** some other rooms, best first.
Draw an arrow from each student to the owner of the room they want most. Because every
student has exactly one arrow, **the arrows must form at least one closed loop**.
A loop is a swap everyone in it likes: each person takes the next person's room.

```
  CS-2026-0003 (lives in J A-201) ──wants──▶ CS-2026-0004 (lives in J B-201)
        ▲                                              │ wants
        │                                              ▼
        └──────────────wants─────────────── CS-2026-0005 (lives in J A-301)
```

Direct 1:1 swapping can never find that 3-way loop, because no two of them want each
other's room.

## Top Trading Cycles, step by step

Repeat until nobody is left:

1. Each remaining student points at the **owner of their best room that is still available**.
   If none of their choices is left, they point at themselves.
2. Find every closed loop of pointers. Each loop is carried out at once: every member
   takes the room of the student they pointed at.
3. A student pointing at themselves forms a loop of one: they **keep their room** (unmatched).
4. Remove everyone who was in a loop, and their rooms. Go back to step 1.

Code: `top_trading_cycles()` in `engine/ttc.py`.

## Worked example: the demo pool

The seeded demo data puts 12 requests in the pool (tracking IDs `CS-2026-0001` … `0012`).
In round 1 everyone points at their first choice:

| Request | Lives in | First choice | Points at |
|---|---|---|---|
| 0001 | J A-101 | J B-101 | 0002 |
| 0002 | J B-101 | J A-101 | 0001 |
| 0003 | J A-201 | J B-201 | 0004 |
| 0004 | J B-201 | J A-301 | 0005 |
| 0005 | J A-301 | J A-201 | 0003 |
| 0006–0009 | K A-101, B-101, A-201, B-201 | the next room in the loop | the next student |
| 0010 | J B-301 | J A-101 | 0001 |
| 0011 | J A-102 | J A-101 | 0001 |
| 0012 | K A-301 | K B-301 (owner not in pool) | itself |

Round 1 finds: the **2-way** loop 0001 ↔ 0002, the **3-way** loop 0003 → 0004 → 0005, the
**4-way** loop 0006 → 0007 → 0008 → 0009, and 0012 pointing at itself (keeps its room).
In round 2, 0010 and 0011 both wanted J A-101, which is now gone. They have no choices left,
so they keep their rooms.

Result: **9 of 12 matched, Match Yield 75%**. Direct 1:1 swaps alone would only find
0001 ↔ 0002: **2 of 12, 16.7%**. The staff page's *Compare* button shows exactly this.

## Rooms with more than one bed

Preferences are for **rooms**, but TTC trades **seats**. A double room has two seats with
two owners. The engine turns "I want room X" into "I want room X's seats, in seat-ID order".
So if either occupant of X is in the pool, you can take their seat; if both are, the
lower seat ID is tried first. This rule makes the result the same every time.

## "Any room like this" choices

A student can also rank a **room type**: a hostel plus, optionally, the number of beds, AC
or not, and a floor. Before calling the engine, the server (`_wanted_seats()` in
`services/matching.py`) turns each choice into seats, best choice first: an exact room
gives its seats; a room type gives the seats of every matching room in that hostel, in room
order, except the student's own room. A seat already listed by an earlier choice is not
listed again. So the engine itself never needs to know about room types. When a student
gets a seat, the choice they "got" is the first of their choices that matches that room.

## Lecture slots use the same engine

For the faculty slot exchange (`services/slots.py`), each open slot request is one
participant: the **slot offered** plays the part of the seat, and the **ranked slots** are
what it wants. The same `top_trading_cycles()` finds the chains. When staff approve a slot
chain, each teacher and their course move to the slot they receive; the time and the hall
of every slot stay where they are. The seeded slot pool gives one 3-way chain and leaves 1
teacher unmatched. Slot rounds are always TTC (there is no 1:1 comparison for slots), and
they are saved as `match_runs` rows with the algorithm name `slot_ttc`.

## When rounds run

Staff can run a round by hand at any time. They can also switch on **automatic rounds**
every N hours (1 to 336). The server's background check, every 30 seconds, runs a saved
TTC room round once one is due. If several rounds were missed while the server was off, it
runs only one and moves the next time forward. Automatic rounds are for rooms only; slot
rounds are always started by staff.

## Guarantees (from the proposal, section 5.2)

| Guarantee | Plain meaning | How we check it |
|---|---|---|
| **Nobody is worse off** (individual rationality) | You only ever move to a room you listed above your own | Test: on 50 random pools, every assigned seat is in that student's acceptable list |
| **Pareto efficient** | No other assignment makes someone happier without making someone else unhappier | A known property of TTC (Shapley & Scarf, 1974) |
| **Strategy-proof** | Ranking rooms honestly is always your best move; lying can't get you a better room | A known property of TTC |
| **Core-stable** | No group can break away and swap among themselves to all do strictly better | A known property of TTC |

## Speed

Each round finds loops in one pass over the students. A student's pointer only moves
forward in their list, because a taken room never comes back. So the total work is at most
about *n* rounds × *n* students, **O(n²)** in the worst case. In practice it's much faster:
our test runs **2,000 students in about 0.1 seconds**.

## The comparison: direct 1:1 swaps only

`pairwise_swaps()` in `engine/pairwise.py` is the simpler method the proposal compares against.
It pairs two students when each listed the other's room, best combined rank first, and nobody
is in two pairs. It is only ever run as a dry run, never used to save real swaps.

## Match Yield

`match_yield(result, pool_size)` = students placed in a chain ÷ students in the pool × 100,
rounded to one decimal. The proposal's target is **at least 60%** on a pool of 100.

## Files

| File | Contents |
|---|---|
| `structures.py` | `Participant(id, seat, wants)`, `Cycle`, `Round`, `MatchResult`, `validate()` |
| `ttc.py` | `top_trading_cycles()` and its loop finder |
| `pairwise.py` | `pairwise_swaps()` |
| `metrics.py` | `match_yield()`, `cycle_length_counts()` |

The engine has no idea whether it is trading beds or lecture slots: it only sees IDs.
