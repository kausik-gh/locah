# LOCAH — Instructions for Codex

Before doing any work in this repository, read the canonical LOCAH
specification documents in [`Documentations/`](Documentations/) (01 through
12). Document 12 (`12-implementation-blueprint-and-engineering-execution-plan.md`)
is the terminal engineering authority — where documents conflict, Document 12
wins, per the conflict order already established by the project. Do not
reinterpret or redesign the product; these documents are the source of truth,
not a starting point for your own design.

## Non-negotiable architectural invariants

- **Business is the tenant.** Location is subordinate to Business, never the
  reverse.
- **Authorization is server-authoritative.** The client never decides what a
  user is allowed to do.
- **RLS is defense in depth**, not the primary authorization mechanism — it
  backs up server-side checks, it does not replace them.
- **Apps do not import other apps.** Cross-app communication happens through
  public contracts (`packages/contracts`) and domain events, never direct
  imports across `apps/*`.
- **Websites are structured content**, generated and edited through the
  defined page/section model — not arbitrary source-code generation.
- **Payments are separated**: platform billing (what the platform charges the
  business) is a distinct concern from merchant collection (what the business
  charges its own customers). Do not conflate the two.
- **Implementation is staged.** Do not build or claim Stage 2+ scope while
  Stage 1 is still in progress, and do not skip ahead of the plan in
  `Documentations/11-first-launch-scope-and-implementation-plan.md` /
  `12-implementation-blueprint-and-engineering-execution-plan.md`.

## Frontend build pass

Frontend/product work is specified in [`docs/build/`](docs/build/):

- `LOCAH-BUILD-SPEC.md` — product and page decisions, already made. Execute
  them; do not re-open them.
- `EXECUTION-PLAN.md` — the phased build order, each phase ending in a check
  that must pass.

Three visual contexts exist and must not converge: `locah-public` (marketing +
Marketplace), `locah-app` (Workspace — its tokens are locked), and `locah-site`
(a tenant's published website, styled only from that business's own theme).
**No LOCAH brand colour may appear on a tenant website** beyond the single
footer attribution.

## Reporting on code and tests

Do not claim code is tested unless it was actually executed. "Written" and
"statically verified" (typechecked/linted) are not the same as "tested" —
keep those claims distinct, and say plainly when something could not be run
(missing dependency, no network, no local Postgres, etc.) rather than
implying it was verified.

## Scope of this file

This file exists to orient a new agent quickly. Do not expand it into general
project documentation — architectural detail belongs in `Documentations/`,
not here.
