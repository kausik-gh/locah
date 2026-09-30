# Branch cleanup manifest

Prepared 2026-09-30 on `claude/final-release-candidate` after `git fetch --all --prune`.
Deletion happened only after final `main` contained the release and each
branch was re-checked with `git merge-base --is-ancestor <head> main` — see
**Deleted** at the end (18 branches, 2026-09-30). The table below is the
audit as prepared.

Reference commit for "included": the release lane head at the time of the
audit (`3a75f55`, which contains the integration head `a2047cb` and a
reconciliation merge of `main` `9c21d46`). "Unique" = commits on the branch
not reachable from the release lane.

## Remote branches

| Branch | Head | Merge base w/ release | Unique | Purpose | In release? | Superseded by / notes | Action |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `main` | `9c21d46` | `1cb02e1` | 0 now (was 1) | Default branch | YES (merged in `2b34513`) | Its "save" commit: older Kitchen copy (release versions kept), TECHNOVA2026 files (kept), `.agents/skills/apple-design` gitlink with no `.gitmodules` (broken; not carried) | **KEEP** — fast-forward to the final tested release |
| `claude/final-release-candidate` | release head | — | — | Closure lane | — | — | **KEEP** until main == release, then DELETE_AFTER_MAIN |
| `claude/phase-b-final-integration` | `a2047cb` | `a2047cb` | 0 | Integration lane (packets A–K + wiring + wrap) | YES | release lane | **DELETE_AFTER_MAIN** (after release tag) |
| `claude/compassionate-allen-hlpq6p` | `2239d24` (at audit) | `d531356` | 8 | **Website Creative v4 — active in another session** | NO | Merges cleanly into the release lane today (dry run: 0 conflicts). Its migration `…website_v4_media_provenance_and_documents` first shared version 20261001100000 with the WhatsApp/calling migration; the Website-v4 session merged the integration branch and moved its own file to 20261001110000, so the release lane keeps WhatsApp at 20261001100000 (a brief rename in `3a75f55` was reverted). | **KEEP** — do not touch; integrate its FINAL head when it reports SAFE_TO_INTEGRATE |
| `cashfree-sandbox` | `8b495b8` | `9659394` | 1 | Uncommitted Cashfree WIP checkpoint (self-described unreviewed/untested), 140 commits behind | NO | See Cashfree audit (FINAL-RELEASE-HANDOFF / Payments section): port deliberately into the current kernel, never merge | **PORT**, then ARCHIVE (tag) and delete after release |
| `claude/p2-02-memberships-wip` | `88ca43c` | `88ca43c` | 0 | Packet A | YES (`7425356`) | — | **DELETE_AFTER_MAIN** |
| `claude/sleepy-gauss-ou1t3i` | `1cb02e1` | `1cb02e1` | 0 | Old Claude lane (P2-01 assignment scope, stage engine) | YES (ancestor) | integration | **DELETE_AFTER_MAIN** |
| `claude/wonderful-newton-eiw7jn` | `9fe343c` | `9fe343c` | 0 | Old Claude lane (P1-09 reviews/compliance WIP) | YES (ancestor) | integration | **DELETE_AFTER_MAIN** |
| `parallel/antigravity-growth` | `e48fd60` | `e48fd60` | 0 | Growth first pass | YES (ancestor of growth-hardening) | `parallel/cursor-growth-hardening` | **DELETE_AFTER_MAIN** |
| `parallel/codex-attendance` | `f8a1348` | `f8a1348` | 0 | Packet J | YES (`8ff25d7`) | — | **DELETE_AFTER_MAIN** |
| `parallel/codex-documents-forms` | `d070a7e` | `d070a7e` | 0 | Packet K | YES (`74d7b26`) | — | **DELETE_AFTER_MAIN** |
| `parallel/codex-projects-jobs-academics` | `e821a63` | `e821a63` | 0 | Packet D | YES (`c40f853`) | — | **DELETE_AFTER_MAIN** |
| `parallel/cursor-dispatch` | `2b115c6` | `2b115c6` | 0 | Packet H | YES (`c111ce6`) | — | **DELETE_AFTER_MAIN** |
| `parallel/cursor-growth-hardening` | `8921222` | `8921222` | 0 | Packet I | YES (`7550111`) | — | **DELETE_AFTER_MAIN** |
| `parallel/cursor-inventory-field` | `7245f54` | `7245f54` | 0 | Packet C | YES (`2c4bfc9`) | — | **DELETE_AFTER_MAIN** |
| `parallel/cursor-kitchen` | `ccf09ff` | `ccf09ff` | 0 | Packet G | YES (`839b465`) | — | **DELETE_AFTER_MAIN** |
| `parallel/cursor-queue-tasks` | `25a0d69` | `25a0d69` | 0 | Packet F | YES (`472a0ea`) | — | **DELETE_AFTER_MAIN** |
| `parallel/cursor-quotes` | `b52002c` | `b52002c` | 0 | Packet E | YES (`d7ed1a2`) | — | **DELETE_AFTER_MAIN** |
| `parallel/cursor-supply-b2b` | `0d3c80f` | `0d3c80f` | 0 | Packet B | YES (`229a396`) | — | **DELETE_AFTER_MAIN** |

## Local-only branches (this Mac, never pushed)

| Branch | Head | Unique | Content | Action |
| --- | --- | --- | --- | --- |
| `backup-before-reset` | `22333ee` | 1 | "Saving changed" — 30 files (permissions, team, invitations, business settings, media); an older snapshot taken before a reset | **KEEP locally** — founder to decide; if wanted, push as an `archive/` tag. No secret-like file names found. |
| `web-builder-lovable` | `d8c143c` | 2 | Website builder quality work + a "pre-switch" WIP (≈228 files; site CSS, interview UI, site-lab script) | **KEEP locally** — likely overlaps Website-v4; the Website-v4 owner should confirm nothing unique is needed before it is archived. |

## Deletion checklist (after final main)

1. Final release commit is on `main`; release tag pushed.
2. For each DELETE_AFTER_MAIN branch: `git merge-base --is-ancestor <head> origin/main` → must print success.
3. Website-v4 only after its final head is in `main` and its gate re-ran on the final product.
4. `cashfree-sandbox` only after the Cashfree port/obsolescence notes are recorded and an `archive/cashfree-sandbox` tag exists.
5. Delete with `git push origin --delete <branch>`; record each deletion below.

## Deleted

2026-09-30, after `main` = `0fe5026` (release tag `locah-demo-2026-09-30-r2`), the
hosted migration and the Railway deploy from `main`. Each branch was
re-checked immediately before deletion.

| Branch | Head | Check |
| --- | --- | --- |
| `claude/p2-02-memberships-wip` | `88ca43c` | ancestor of main |
| `claude/phase-b-final-integration` | `a2047cb` | ancestor of main |
| `claude/sleepy-gauss-ou1t3i` | `1cb02e1` | ancestor of main |
| `claude/wonderful-newton-eiw7jn` | `9fe343c` | ancestor of main |
| `claude/compassionate-allen-hlpq6p` (Website-v4) | `f2c6353` | ancestor of main (merged in `9a5248b`; full gate re-run on the final product) |
| `parallel/antigravity-growth` | `e48fd60` | ancestor of main |
| `parallel/codex-attendance` | `f8a1348` | ancestor of main |
| `parallel/codex-documents-forms` | `d070a7e` | ancestor of main |
| `parallel/codex-projects-jobs-academics` | `e821a63` | ancestor of main |
| `parallel/cursor-dispatch` | `2b115c6` | ancestor of main |
| `parallel/cursor-growth-hardening` | `8921222` | ancestor of main |
| `parallel/cursor-inventory-field` | `7245f54` | ancestor of main |
| `parallel/cursor-kitchen` | `ccf09ff` | ancestor of main |
| `parallel/cursor-queue-tasks` | `25a0d69` | ancestor of main |
| `parallel/cursor-quotes` | `b52002c` | ancestor of main |
| `parallel/cursor-supply-b2b` | `0d3c80f` | ancestor of main |
| `cursor/gemini-activation-audit` | `e27dfe9` | not an ancestor (cherry-picked as `747a4d4`); its only change, `GEMINI-ACTIVATION-AUDIT.md`, is byte-identical in main; tag `archive/gemini-activation-audit` |
| `cashfree-sandbox` | `8b495b8` | not merged by design; disposition in `FINAL-RELEASE-HANDOFF.md` (CASHFREE) and `6fec540`; tag `archive/cashfree-sandbox` |

Kept: `main`; `claude/final-release-candidate` (the release worktree's
branch, equal to main's release commit — delete once no further release
documentation is pushed from it). Local-only `backup-before-reset` and
`web-builder-lovable` untouched (founder's decision, see above). Local
branches in the other worktrees (`/locah`, `/locah-gemini-audit`) untouched.

Tags: `locah-demo-2026-09-30-r2` (release, `0fe5026`),
`locah-demo-2026-09-30` (`dfe2995`, superseded — its migration set collided
with the hosted history), `archive/cashfree-sandbox`,
`archive/gemini-activation-audit`.
