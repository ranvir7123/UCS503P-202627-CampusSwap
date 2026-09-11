# Viva question bank

Quiz each other with these. Cover the answer, say yours out loud, then compare. Answers
are short on purpose: explain them in your own words.

## The project

**1. What problem does CampusSwap solve?**
Students who want to change hostel rooms depend on finding a direct swap partner through
scattered WhatsApp messages. CampusSwap collects everyone's choices and finds multi-way
swap chains automatically, then tracks confirmation and approval.

**2. Who are the users?** Students (submit, confirm or decline) and hostel staff / the
warden (run rounds, approve).

**3. What are your two features?** (1) Submit a ranked request of up to 5 rooms. (2) Run a
TTC matching round and see the chains and Match Yield. Plus confirm / decline / approve.

**4. What was your Phase 1 success definition, and did you meet it?** Accept a request, save
it, run a match, show the result. Yes: all four work with real data and are tested over HTTP.

## The algorithm

**5. Explain TTC in one sentence.** Everyone points at the owner of their favourite
available room; every closed loop swaps; remove them and repeat.

**6. Why must a cycle exist each round?** Every person points at exactly one person, and
there are finitely many people, so following the arrows must eventually loop back.

**7. Why is TTC better than 1:1 swapping?** It finds 3-way and longer chains. On our demo pool:
75% matched versus 16.7%.

**8. Can anyone end up worse off?** No. You only point at rooms you ranked, and if none is
left you keep your own.

**9. What does strategy-proof mean here?** Ranking honestly is always your best move;
lying about preferences can never get you a better room.

**10. Why not Gale-Shapley?** That's for two-sided matching (both sides have preferences).
Ours is a housing market: people already own rooms and trade them. TTC is the standard
algorithm for that.

**11. Time complexity?** O(n²) worst case; 2,000 students in about 0.1 s in our test.

**12. How do you handle double rooms?** Students own seats (beds). Ranking a room means
ranking its seats in seat-ID order.

**13. What is Match Yield?** Matched students ÷ students in the pool × 100. Target ≥ 60%.

## Design

**14. Describe the architecture.** Pages → FastAPI routes → services (rules) → SQLite, with
the TTC engine as a separate pure-Python module that the matching service calls.

**15. Why keep the engine separate?** To test it alone with made-up data, and to reuse it
later (faculty slots) without touching web or database code.

**16. What is a transaction and where do you use one?** A group of changes that all happen or
none do. Every request (e.g. a whole matching round) commits once at the end.

**17. Why SQLite?** Real SQL with transactions, nothing to install; easy to switch to PostgreSQL.

**18. How is login secured?** Salted `scrypt` password hashes; a random session token in an
HttpOnly cookie; only the token's hash is stored; sessions expire after 12 hours.

**19. How do you stop a student using admin features?** The server checks the role on every
admin endpoint (`current_admin`) and returns 403; hiding the page is not relied on.

**20. How do you stop HTML injection (XSS)?** All server text is escaped before it goes into
the page (`html` helper in `ui.js`).

**21. What happens if someone declines?** The chain is cancelled; the decliner's request
closes; everyone else goes back into the pool for the next round.

**22. What if nobody answers in 48 hours?** The chain is dissolved the next time a round runs
or someone answers; people who never answered are withdrawn, people who accepted return to the pool.

## UML diagrams

**23. What does your Use Case diagram show?** The two actors and 14 use cases, with
«include» for mandatory sub-steps and «extend» for the optional dry run.

**24. Include vs extend?** Include always happens (submit → validate). Extend happens only
sometimes (dry run extends run).

**25. Composition vs aggregation vs association?** Composition: the part dies with the whole
(seat and room). Aggregation: a whole that shares parts that can live on (not used here).
Association: a plain link between independent things (student and seat).

**26. Why is Student a subclass of User?** Both log in the same way and share fields;
students add roll number, gender, year and branch. One table stores both.

**27. What do `loop` and `alt` mean in the sequence diagram?** Loop repeats (each member
confirms). Alt picks one branch (all accepted vs. someone declined / deadline passed).

**28. Why swimlanes in the activity diagram?** To show who does each step: student, system or warden.

## Process and testing

**29. How did you test it?** 90 automated tests: the engine on hand-made and random pools,
every service rule, and full HTTP flows. The pages were checked in a browser by hand.

**30. What is CI and do you use it?** Continuous integration: GitHub Actions runs the tests
on every push and pull request.

**31. How did you work as a team in Git?** Work on a `prototype` branch, merged into `master`
by pull request after tests pass; weekly journals in `journals/`.

**32. What was hardest?** (Answer honestly from your own part.) For example: the confirmation
rules for declines and deadlines, or drawing a swap ring for any chain length.

## Limits and future

**33. What isn't built yet?** Thapar single sign-on, notifications, the PDF approval form, the
faculty slot module, a background timer. All data is synthetic.

**34. How would you scale it?** PostgreSQL instead of SQLite, a background worker for very
large rounds, and notifications. TTC itself is already fast enough.

**35. How would the faculty slot feature reuse the engine?** Slots become the "seats" and
preferred slots become "wants"; the engine code doesn't change.
