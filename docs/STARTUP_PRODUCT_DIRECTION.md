# TRIFECTA — MASTER STARTUP PRODUCT DIRECTION

## PURPOSE

This document is the permanent product and engineering direction for Trifecta.

Read this BEFORE implementing any future feature prompt.

Individual implementation prompts define the immediate task, but they must be interpreted within this wider product direction.

Do not follow feature prompts mechanically in isolation.

Before implementing anything, determine:

1. How does this help the business at its CURRENT stage?
2. Does equivalent functionality already exist?
3. Is this actually needed now, or is it enterprise complexity being introduced too early?
4. What future Trifecta feature will depend on this?
5. Can the architecture support the future need without implementing that future complexity today?
6. Does the proposed implementation preserve existing security, performance, historical-data, financial, scheduling, and inventory invariants?

If an individual prompt appears to conflict with this master direction:

- preserve correctness;
- avoid unnecessary scope;
- implement the smallest architecture that supports the stated current need;
- explain the conflict in the final report.

Do not silently turn Trifecta into enterprise software.

============================================================
1. WHAT TRIFECTA IS
============================================================

Trifecta is being built initially for a SMALL CAR-CARE / DETAILING STARTUP.

The business is still in the stage of:

- acquiring customers;
- building reputation;
- organizing daily operations;
- scheduling a small number of teams/vans;
- controlling service quality;
- collecting payments;
- tracking basic costs;
- retaining customers;
- understanding whether services are profitable.

The immediate product objective is NOT:

"build software capable of running a 100-branch corporation."

The immediate objective is:

> Make a small car-care business extremely easy to operate from customer booking through payment and repeat business.

The startup operating loop is:

CUSTOMER ACQUISITION
→ BOOKING
→ SCHEDULING
→ TEAM ASSIGNMENT
→ SERVICE DELIVERY
→ QUALITY CONTROL
→ PAYMENT
→ COST/INVENTORY RECORDING
→ CUSTOMER FOLLOW-UP
→ REPEAT / REFERRAL BUSINESS

Every major startup-stage feature should materially improve one or more parts of this loop.

============================================================
2. CORE STARTUP PRODUCT PRINCIPLE
============================================================

Before adding a feature, ask:

> Does this help us sell, schedule, perform, collect, understand costs, or retain customers right now?

If YES:
it may belong in the startup roadmap.

If NO:
it should normally wait.

Engineering time is a limited business resource.

Features that solve hypothetical future enterprise problems can actively harm the startup by consuming time that should be spent on customer-facing and operational capabilities.

============================================================
3. DO NOT OVERBUILD FOR SCALE WE DO NOT HAVE
============================================================

Do not implement features merely because a mature chain might eventually need them.

Examples that are NOT startup priorities:

- complex supplier management;
- Purchase Orders;
- Goods Receipt Notes;
- accounts payable;
- vendor portals;
- multi-warehouse purchasing;
- FIFO/LIFO inventory valuation;
- sophisticated procurement approvals;
- multi-branch price books;
- corporate territory management;
- complex payroll;
- enterprise HR;
- advanced BI warehouses;
- forecasting engines;
- automated purchasing;
- complex tax/accounting engines;
- highly configurable workflow engines;
- generic rule builders;
- microservices merely for future scale;
- Redis/event infrastructure without measured need.

These may become valuable later.

Do not delete architectural options for them, but do not build them prematurely.

============================================================
4. STARTUP ROADMAP
============================================================

The planned startup roadmap is approximately:

PHASE 1
Service Catalogue, Pricing & Business Configuration

PHASE 2
Smart Scheduling & Automatic Team Assignment

PHASE 3
Service Consumption Templates & Automatic Inventory Usage

PHASE 4
Customer Communication Automation

PHASE 5
Payments, Deposits & No-Show Protection

PHASE 6
Discounts, Promotions & Referrals

PHASE 7
Reviews, Ratings & Customer Feedback

PHASE 8
Owner Daily Operations Dashboard / Startup Business Intelligence

This ordering may change if real operational needs justify it.

Do not implement later phases merely because they are documented here.

The purpose of knowing the roadmap is to ensure today's architecture does not make tomorrow's implementation unnecessarily difficult.

============================================================
5. PHASE 1 DIRECTION — SERVICES
============================================================

Trifecta should have an authoritative service catalogue.

The owner should control:

- service name;
- description;
- active/inactive;
- vehicle-type pricing;
- expected duration;
- mobile/shop availability;
- add-ons;
- relevant business booking settings.

The customer website and staff system must consume the same authoritative configuration.

Existing booking commercial history must remain immutable through snapshots.

The service catalogue is important because it becomes the foundation for:

- pricing;
- booking;
- scheduling;
- team assignment;
- automatic inventory usage;
- loyalty;
- reports;
- future job profitability.

Do not scatter service rules into client-side constants.

============================================================
6. PHASE 2 DIRECTION — SMART TEAM ASSIGNMENT
============================================================

Trifecta should eventually automatically assign confirmed bookings to appropriate available teams.

STARTUP VERSION:

Keep the first algorithm simple.

It should consider primarily:

- active teams;
- team working status;
- existing bookings;
- booking start time;
- expected service duration;
- default travel/turnaround buffer;
- workload/fairness.

It should NOT initially require:

- live GPS;
- van tracking;
- route optimization;
- traffic prediction.

Example desired behavior:

Team A:
09:00 job

Team B:
free

New booking:
12:00

Even if Team A could theoretically finish in time, prefer Team B where reasonable so Team A has travel/cleanup/delay buffer.

A simple scoring architecture is appropriate.

Possible conceptual factors:

HARD RULES:
- no actual schedule conflict;
- team must be operational/available;
- required service window must fit.

PREFERENCES:
- completely free team;
- fewer jobs that day;
- longest idle window;
- avoid unnecessary back-to-back work;
- fair distribution.

Manager must always be able to override automatic assignment.

Manual overrides must not immediately be undone automatically.

============================================================
7. FUTURE LOCATION-AWARE ASSIGNMENT
============================================================

Later, when the business has enough jobs for geography to matter materially, Phase 2 can evolve.

Future scoring may include:

- previous job location;
- next job location;
- current van/team position;
- Google Routes travel time;
- traffic;
- expected completion;
- distance;
- workload.

Example:

Team A finishes on Yas Island.

Team B finishes in Khalifa City.

Next customer is on Saadiyat.

The scheduler may prefer Team A.

DO NOT implement this now unless specifically requested.

But scheduling architecture should not make geographic scoring impossible later.

============================================================
8. SCHEDULING MUST USE BOOKING SNAPSHOTS
============================================================

Confirmed bookings should store their expected operational duration.

Example:

Service today:
120 min

Booking confirmed:
expected_duration_minutes = 120

Owner later changes service:
150 min

Existing booking remains:
120 min

Future bookings:
150 min

The scheduler must eventually use the booking snapshot, not the mutable current service definition.

============================================================
9. PHASE 3 DIRECTION — SERVICE CONSUMPTION
============================================================

Trifecta already has inventory infrastructure.

The startup goal is NOT perfect warehouse accounting.

The goal is:

> Automatically estimate and record consumables used when a service is completed.

Conceptually this is similar to CorePOS recipes.

Restaurant:

Burger
- beef 180 g
- sauce 25 g
- cheese 1
- bun 1

Trifecta:

Standard Wash
- shampoo 50 ml
- wheel cleaner 30 ml
- glass cleaner 15 ml
- tyre dressing 20 ml
- water 80 L

The service configuration defines EXPECTED STANDARD CONSUMPTION.

============================================================
10. EXPECTED VS PERFECT INVENTORY ACCURACY
============================================================

Car-care consumables are less deterministic than restaurant ingredients.

Usage varies due to:

- vehicle size;
- dirt level;
- worker technique;
- dilution;
- weather;
- service conditions.

Therefore Trifecta should treat service consumption quantities as:

EXPECTED STANDARD USAGE

rather than pretend every job consumes the exact physical quantity.

This is still valuable.

Over many jobs the owner can compare:

expected consumption
vs
stock counts / purchasing

and identify:

- excessive use;
- leakage;
- incorrect measurements;
- operational waste.

============================================================
11. AUTOMATIC INVENTORY USAGE
============================================================

When Phase 3 is implemented:

successful job completion should trigger expected inventory usage.

Conceptually:

job completion
→ service snapshot/template
→ calculate expected quantities
→ lock relevant stock rows
→ create inventory usage movements
→ link usage to job
→ update stock
→ commit safely

Reuse the EXISTING inventory engine.

Do not create a second stock ledger.

Preserve:

- tenant isolation;
- append-only movements;
- deterministic locking;
- idempotency;
- stock history.

============================================================
12. INVENTORY MUST NOT BLOCK SERVICE DELIVERY UNNECESSARILY
============================================================

A car-care startup cannot become unable to complete a customer's job merely because the system believes shampoo inventory is zero.

Example:

Physical inventory:
5 litres

System:
0 ml

because somebody forgot to record receipt.

The customer service workflow should not fail.

Preferred behavior:

Job completion succeeds.

Expected stock deduction detects insufficient recorded quantity.

Create an inventory discrepancy / attention state.

Example:

Inventory mismatch

Expected:
60 ml Shampoo

Recorded stock:
20 ml

Manager review required.

Do not silently create nonsensical negative stock.

Do not block customer completion solely because recorded consumables are imperfect.

============================================================
13. FUTURE VEHICLE-SPECIFIC CONSUMPTION
============================================================

Eventually expected usage may vary by vehicle type.

Example:

Standard Wash

Sedan:
40 ml shampoo

SUV:
55 ml

Large SUV:
70 ml

Do not build a complicated consumption matrix unless real testing demonstrates that it materially improves accuracy.

Version 1 may use one service default.

Architecture should allow later refinement.

============================================================
14. JOB COSTING DIRECTION
============================================================

Service consumption should eventually contribute to simple job costing.

Example:

Standard SUV Wash

Revenue:
AED 100

Expected consumables:
AED 5

Later:
labour allocation
travel/fuel
payment fees

This can eventually answer useful startup questions such as:

- Which services make the most money?
- What does an SUV wash actually cost?
- Are expensive detailing packages worth the labour?
- Are consumables growing faster than sales?

Do not turn this into formal accounting software.

============================================================
15. EXPENSES
============================================================

Existing Finance should remain simple.

The startup needs:

- quick expense entry;
- categories;
- void/audit behavior;
- cash reconciliation;
- usable profit/revenue views.

Where useful, expenses may later be attributable to:

- a specific job;
- a service;
- operational period.

Example:

special material purchased for one detailing job.

This should help determine actual job profitability.

Do not create enterprise cost-center accounting.

============================================================
16. PHASE 4 — CUSTOMER COMMUNICATION
============================================================

Communication automation should reduce manual WhatsApp/call workload and improve professionalism.

Important events include:

- booking confirmation;
- booking reminder;
- driver/team on the way;
- arrival;
- delay notice;
- completion;
- payment request;
- cancellation/reschedule;
- review request.

Use the existing durable notification/outbox architecture.

Do not put provider latency in business transactions.

Email already exists.

WhatsApp/SMS may be added when operationally justified.

============================================================
17. PHASE 5 — PAYMENT & DEPOSIT DIRECTION
============================================================

Payments should help:

- reduce no-shows;
- improve cash flow;
- simplify collection.

Potential startup functionality:

- payment links;
- booking deposits;
- configurable deposit requirements;
- paid/unpaid visibility;
- pay-after-service;
- cash tender;
- simple refunds/cancellations where needed.

Do not build a payment processor.

Use providers.

Never store raw card details.

============================================================
18. PHASE 6 — STARTUP GROWTH FEATURES
============================================================

Once operations are stable, Trifecta should help acquire and retain customers.

Useful simple tools:

- fixed discount;
- percentage discount;
- promo code;
- manager manual discount;
- limited campaign;
- referral reward.

Avoid sophisticated marketing automation initially.

============================================================
19. PHASE 7 — REVIEWS & FEEDBACK
============================================================

After job completion:

ask the customer for simple feedback.

Possible flow:

rating
→ optional comment

Satisfied customers may then be encouraged to leave a public review.

Negative feedback should remain internally visible so the business can address it.

Do not manipulate or suppress legitimate customer feedback.

============================================================
20. PHASE 8 — OWNER DAILY OPERATIONS
============================================================

The startup owner should eventually be able to open one screen and understand today.

Example:

Today's bookings
12

Completed
7

Remaining
5

Revenue collected
AED X

Outstanding
AED Y

Expenses
AED Z

New customers
4

Rewashes / complaints
1

Cash employees are holding
AED X

Low stock
3 items

Do not build enterprise BI.

Show actionable numbers the owner needs every day.

============================================================
21. EXISTING CORE SYSTEMS MUST BE REUSED
============================================================

Before implementing anything, audit existing infrastructure.

Trifecta already has important foundations including:

- FastAPI;
- PostgreSQL/Supabase;
- customer web;
- Expo/React Native mobile;
- guest/auth booking;
- booking availability;
- scheduling;
- teams;
- job lifecycle;
- payments/cash;
- customer profiles;
- loyalty;
- quality controls;
- Finance;
- Inventory;
- service inventory template foundations;
- durable notification outbox;
- mobile persisted cache;
- sync revisions;
- performance telemetry.

Do not create competing implementations.

PATCH / EXTEND existing systems.

============================================================
22. PERFORMANCE DIRECTION
============================================================

Trifecta recently received a dedicated performance pass.

The website is currently perceived as very fast.

Do not regress this.

Mobile architecture includes:

- TanStack Query;
- persisted scoped read cache;
- stale-while-revalidate;
- targeted invalidation;
- sync revisions.

Do not introduce another cache layer.

Important UI rule:

no cache + pending
→ loader

usable data + refresh
→ keep data visible

Never regress to:

data
→ skeleton
→ same data

during background refresh.

============================================================
23. MOBILE PERFORMANCE PRIORITY
============================================================

Do not spend major engineering passes chasing theoretical mobile latency unless measurement demonstrates a meaningful bottleneck.

When adding functionality:

- lazy-load hidden tabs;
- avoid request amplification;
- use authoritative mutation responses;
- update affected cache immediately;
- reconcile quietly;
- avoid broad refreshEverything patterns.

Perceived responsiveness is part of feature quality.

============================================================
24. DATABASE / BACKEND PERFORMANCE
============================================================

Do not optimize blindly.

Preserve current observability:

- request timing;
- SQL count/time;
- connection checkout;
- staff context;
- provider timing;
- cold/warm classification.

Prefer:

- narrow projections;
- bounded queries;
- short transactions;
- SQL aggregates when appropriate;
- request-local reuse;
- correct indexes supported by evidence.

Do not build giant queries merely to reduce query count.

============================================================
25. SECURITY INVARIANTS
============================================================

Never weaken:

- business/tenant isolation;
- staff role enforcement;
- team authorization;
- customer ownership;
- financial authority;
- inventory authority;
- JWT validation;
- idempotency.

Backend remains source of truth.

Web/mobile do not directly write business tables.

Service-role credentials remain backend-only.

============================================================
26. FINANCIAL INVARIANTS
============================================================

Money uses integer minor units.

Never trust client-computed authoritative totals.

Historical commercial snapshots are immutable.

Avoid:

- floating-point money;
- silent changes to historical bookings;
- offline replay of financial writes;
- optimistic fabricated financial totals.

============================================================
27. INVENTORY INVARIANTS
============================================================

Maintain:

- authoritative backend stock;
- append-only movement history;
- tenant/location scope;
- idempotent writes;
- deterministic lock order;
- no silent negative stock;
- transaction correctness.

Automatic service consumption must eventually reuse these guarantees.

============================================================
28. BOOKING INVARIANTS
============================================================

Confirmed bookings preserve snapshots including relevant:

- service;
- price;
- vehicle;
- customer;
- address;
- duration.

Later edits to:

service
customer profile
vehicle profile
price
duration

must not silently rewrite historical bookings.

============================================================
29. STARTUP UX PRINCIPLE
============================================================

The owner should not need technical knowledge to operate Trifecta.

Prefer:

simple settings

over:

generic configuration engines.

Prefer:

"Time between mobile jobs — 60 min"

over:

"Scheduling buffer coefficient."

Prefer:

"Mobile minimum — AED 200"

over:

JSON settings.

============================================================
30. DO NOT CREATE DEAD CONFIGURATION
============================================================

Do not expose settings that nothing currently uses unless:

- they are explicitly being prepared for the immediately following phase;
- and their future consumer is clearly documented.

A settings screen full of non-functional controls is worse than not having the settings.

============================================================
31. FEATURE DECISION FRAMEWORK
============================================================

For every new major feature, classify:

A — Immediate startup value
Helps current daily operations/customer growth.

B — Near-term foundation
Needed by an upcoming startup phase.

C — Future scaling value
Useful when the company becomes substantially larger.

D — Enterprise-only / speculative

IMPLEMENT:
A

USUALLY IMPLEMENT:
B, but only the necessary foundation.

DEFER:
C

DO NOT IMPLEMENT NOW:
D

Include this classification in implementation planning when scope is ambiguous.

============================================================
32. FUTURE SCALE SHOULD BE ENABLED, NOT IMPLEMENTED
============================================================

Example:

Current:
one business with small number of teams.

Future:
multiple branches and vans.

Correct startup architecture:

business_id scoped data
team/location IDs
clean service layer

Incorrect startup architecture:

building an entire regional branch-management platform today.

Design clean boundaries.

Do not build unused user experiences.

============================================================
33. REAL OPERATIONS OVERRIDE ROADMAP
============================================================

The roadmap is guidance, not dogma.

If real business operations reveal that something else is urgently needed:

- broken booking flow;
- customer communication problem;
- payment issue;
- scheduling conflict;
- staff workflow problem;

prioritize the real operational problem.

Do not continue building roadmap features while a high-impact real workflow is broken.

============================================================
34. IMPLEMENTATION BEHAVIOR FOR CODEX
============================================================

For every future feature prompt:

STEP 1
Read this master direction.

STEP 2
Read the current README / architecture documentation relevant to the task.

STEP 3
Audit the current implementation.

STEP 4
Identify what already exists.

STEP 5
Determine immediate startup need.

STEP 6
Determine near-term dependency.

STEP 7
Implement the smallest correct architecture satisfying both.

STEP 8
Preserve invariants.

STEP 9
Test physical end-to-end usability, not only unit behavior.

STEP 10
Report what was deliberately NOT implemented.

============================================================
35. DO NOT BLINDLY FOLLOW IMPLEMENTATION ASSUMPTIONS
============================================================

Individual prompts may contain assumptions about:

- current schema;
- route names;
- migration head;
- existing screens;
- whether something is already implemented.

VERIFY THEM.

If repository reality differs:

use the current repository as authority.

Do not duplicate systems because a prompt assumed something was missing.

Explain meaningful discrepancies in final output.

============================================================
36. DO NOT EXPAND SCOPE SILENTLY
============================================================

If implementing Feature A makes Feature B tempting:

do not automatically implement Feature B.

Example:

Service catalogue introduces duration.

Do:
store duration correctly for future scheduling.

Do NOT:
also implement auto-assignment unless the current phase requests it.

============================================================
37. PREPARE NEXT PHASE WITHOUT IMPLEMENTING IT
============================================================

A strong implementation should make the next planned phase easier.

Examples:

Service catalogue:
→ authoritative duration snapshots.

Then smart scheduling can consume them.

Smart scheduling:
→ clear assignment decisions / timestamps.

Then location-aware scheduling can later add travel scoring.

Service consumption templates:
→ expected quantities.

Then automatic inventory usage can safely consume them.

This is preferred over both extremes:

1. ignoring future requirements entirely;
2. implementing the entire future roadmap at once.

============================================================
38. QUALITY STANDARD
============================================================

A feature is not complete merely because:

pytest passes.

A feature is complete when:

- backend behavior works;
- actual UI is usable;
- authorization is correct;
- mutations physically work;
- data remains correct after refresh;
- loading/error states make sense;
- mobile behavior works;
- web behavior works where applicable;
- historical data remains correct;
- performance does not meaningfully regress.

============================================================
39. DEFAULT PRODUCT QUESTION
============================================================

When uncertain between a sophisticated solution and a simpler one, ask:

> What would make the owner's life easier tomorrow morning?

Prefer that solution unless it creates a correctness/security problem.

============================================================
40. CURRENT NORTH STAR
============================================================

For the startup phase, Trifecta should increasingly achieve this workflow:

Customer discovers business
↓
Customer books easily
↓
Correct price is calculated
↓
System determines capacity
↓
Booking is automatically assigned intelligently
↓
Team sees clear job instructions
↓
Team travels and performs service
↓
Quality is recorded
↓
Expected consumables update automatically
↓
Customer pays
↓
Owner sees revenue/cost/cash status
↓
Customer receives follow-up
↓
Customer returns or refers another customer

The product roadmap should continuously reduce the manual work inside this loop.

============================================================
41. DEFERRED SCALE FEATURES
============================================================

Unless explicitly promoted by a future business need, keep these deferred:

- supplier management;
- purchase orders;
- goods receiving workflows;
- enterprise procurement;
- inventory valuation/accounting;
- complex multi-branch management;
- GPS dispatch optimization;
- route clustering;
- sophisticated forecasting;
- advanced payroll;
- enterprise HR;
- enterprise BI;
- advanced accounting;
- vendor invoice reconciliation.

Their absence is intentional.

============================================================
42. FINAL IMPLEMENTATION REPORT REQUIREMENT
============================================================

Every future Codex implementation should finish by explicitly reporting:

1. Immediate startup problem solved.
2. Existing architecture reused.
3. New architecture introduced.
4. User-facing behavior.
5. Backend/source-of-truth behavior.
6. Historical-data safeguards.
7. Performance impact.
8. Security/authorization.
9. Tests.
10. Physical/manual checks.
11. Migration requirements.
12. Deployment requirements.
13. Environment changes.
14. Next-phase foundation created.
15. Features deliberately deferred.
16. Any master-roadmap conflict discovered.

The final report should distinguish:

IMPLEMENTED NOW

PREPARED FOR NEXT PHASE

DEFERRED UNTIL BUSINESS SCALE JUSTIFIES IT

============================================================
PRODUCT PRINCIPLE
============================================================

Trifecta is not trying to anticipate every problem the company might have in five years.

Trifecta should solve the problems the company has today extremely well, while building clean enough foundations that tomorrow's problems can be added without rewriting the system.

Build for:

today's business

with:

tomorrow's architecture

but NOT:

tomorrow's unnecessary complexity.