# Everyone: the whole system

Every team member must be able to explain everything on this page.

## The 30-second pitch

> Hostel rooms are allocated once and rarely change. Students who want to move have to find
> someone who wants their room *and* has a room they want, usually through WhatsApp.
> CampusSwap collects everyone's ranked choices and runs the **Top Trading Cycles**
> algorithm, which finds **chains** of swaps (A takes B's room, B takes C's, C takes A's)
> where everyone ends up in a room they prefer. On our demo data it matches **75%** of
> students, compared with **16.7%** for direct 1:1 swaps. Students confirm, the warden
> approves, and the rooms change hands.

## The problem

- Rooms are fixed for the semester; moving means trading with someone.
- Direct 1:1 swaps are rare: two people must each want exactly the other's room.
- Requests are scattered (WhatsApp, notice boards); nobody sees the full picture.
- Paper forms, no tracking: students don't know if anything is happening.

## The solution in five lines

1. Each student ranks up to 5 rooms and submits (**feature 1**).
2. The warden runs a matching round (**feature 2**).
3. TTC: everyone points at the owner of their best available room; every closed loop is a
   swap; remove those students; repeat.
4. Each student in a chain confirms within 48 hours; one "no" cancels that chain.
5. The warden approves a fully confirmed chain, and the seats change hands.

## One picture of the system

```
Browser pages ──HTTP/JSON──▶ FastAPI routes ──▶ Services (rules) ──▶ SQLite database
                                                     │
                                                     └──▶ TTC engine (pure Python)
```

- **Pages** show things and call the API. No rules there.
- **Routes** check who is logged in, then call a service.
- **Services** hold every rule and save changes in one transaction.
- **Engine** only does the maths, so it can be tested alone.

## Numbers to remember

| Number | What it is |
|---|---|
| 5 | The most rooms a student can rank |
| 48 hours | Time every chain member has to confirm |
| 12 → 9 | Demo pool: 12 requests, 9 matched (one 2-way, one 3-way, one 4-way chain) |
| 75% vs 16.7% | Match Yield on the demo pool: TTC vs 1:1 swaps only |
| 80% | Match Yield after the 3 demo students add their 3-way chain (12 of 15) |
| ≥ 60% | The proposal's Match Yield target |
| 90 | Automated tests; they run on GitHub for every push |
| ~0.1 s | Time for TTC on 2,000 students in our tests |
| O(n²) | Worst-case running time of TTC for *n* students |

## Words you must be able to explain simply

| Word | Plain meaning |
|---|---|
| **Top Trading Cycles (TTC)** | The matching method: point at the owner of your favourite available room, carry out every closed loop, repeat |
| **Cycle / chain** | A loop of students where each takes the next one's room |
| **Match Yield** | Share of students in the pool who got placed in a chain |
| **Pareto efficient** | You can't make anyone happier without making someone else unhappier |
| **Strategy-proof** | Ranking your true preferences is always your best move |
| **Dry run** | Running the matching to see the result without saving anything |
| **API** | The list of addresses (like `/api/requests`) the pages use to talk to the server |
| **Transaction** | A group of database changes that all happen, or none do |
| **Hashing** | Scrambling a password one way, so the original can't be read back |
| **Session cookie** | A random ticket the browser shows on every request to prove who you are |
| **CI (continuous integration)** | GitHub runs all tests automatically on every push |

## What is not built (say this confidently)

Real Thapar single sign-on, notifications, the PDF approval form, the faculty slot module,
and a background timer for deadlines. All data is made up. See [Limitations](../limitations.md).
