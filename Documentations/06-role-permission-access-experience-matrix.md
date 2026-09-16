# Role, Permission & Access Experience Matrix

**Document:** 06  
**Document Status:** Canonical foundation  
**Version:** 1.0  
**Date:** July 2026  
**Authority:** Access experience and authorization-state projection  
**Depends On:** `01-vision-document.md` · `02-product-experience-bible.md` · `03-business-kernel-specification.md` · `04-master-product-specification.md` · `05-user-context-journey-navigation-architecture-specification.md`

---

# 1. Purpose, Scope and Non-Goals

## 1.1 Purpose

This document defines how authorization, scope, Commercial Entitlement, module state, and policy become a coherent user experience.

Its governing question is:

> Given this person, in this active context, scope, and state, what can they see, enter, understand, and do—and what experience occurs when access is unavailable, restricted, or requires approval?

This document governs:

1. experience-level access evaluation;
2. actor, context, role, and permission-template access posture;
3. visibility and navigation behavior caused by access state;
4. canonical restricted, read-only, approval, and recovery experiences;
5. Business-wide, Location-scoped, and multi-Business access behavior;
6. invitation, membership, and permission-change experience;
7. sensitive-action treatment;
8. Platform Super Admin access and attribution;
9. deep-link access outcomes; and
10. audit and attribution expectations visible to product experiences.

## 1.2 Source authority

| Source | Authority used here |
|---|---|
| Document 01 — Vision | Strategic platform intent and long-term contexts |
| Document 02 — Product Experience Bible | Clarity, progressive complexity, trust, surface-appropriate behavior, and access-state language quality |
| Document 03 — Business Kernel Specification | Current domain and enforcement concepts for Business membership, roles, module grants, capabilities, RLS, and elevated administration |
| Document 04 — Master Product Specification | Product, page, workflow, settings, and existing permission inventory |
| Document 05 — User Context, Journey & Navigation Architecture | Governing context model, approved core roles/templates, Location scope, Entitlement separation, shells, routes, journeys, and access-sensitive navigation |

Where Documents 03 or 04 conflict with the approved decisions recorded in Document 05, Document 05 governs this experience matrix and the conflict is recorded in Section 19.

## 1.3 Non-goals

This document does not redefine:

- canonical permission enforcement semantics in the Business Kernel;
- the complete product feature or page inventory;
- navigation shells, route namespaces, or authentication routing;
- physical database tables or row-level-security policies;
- API or event contracts;
- Commercial Entitlement pricing, billing, or metering;
- exhaustive per-module action permissions;
- detailed page layouts or component specifications; or
- future enterprise administration structures.

Navigation architecture remains in Document 05. This document defines the experience produced by access evaluation within that architecture.

## 1.4 Normative principles

**ACCESS-001 — Context first:** A Platform Identity has no single global Business authority. Access is evaluated in the active Personal, Business, Platform Administration, or other explicitly supported context.

**ACCESS-002 — Independent gates:** Entitlement, module state, Location availability, membership scope, permission, and workflow policy are separate gates. One gate passing never implies another.

**ACCESS-003 — Security independent of visibility:** Hidden navigation is not authorization. Every protected route, resource, and action MUST be independently enforced and revalidated.

**ACCESS-004 — Correct category, safe disclosure:** The experience SHOULD explain the true category of unavailability where safe, without revealing private resources, memberships, security controls, or Business data.

**ACCESS-005 — No stale authority:** Remembered context, cached UI, an open page, or a previously visible action never preserves access after authority changes.

**ACCESS-006 — Smallest useful recovery:** A restricted experience offers only recovery actions the person can legitimately perform.

---

# 2. Access Evaluation Model

## 2.1 Conceptual sequence

The access experience is derived through the following sequence:

```text
Platform Identity or bounded guest authority
→ Active operating context
→ Relevant Business membership and membership state
→ Allowed Business/Location/assignment scope
→ Commercial Entitlement
→ Module enabled/configured state and contextual availability
→ Role and exact permission
→ Resource state and workflow/policy requirements
→ Resulting experience
```

This is a conceptual explanation order, not a prescribed query plan. Enforcement MAY evaluate safe gates earlier for security or efficiency, but it MUST produce no unauthorized disclosure and MUST preserve the distinctions in this model.

Not every journey uses every gate. Public browsing may need no Business membership. A bounded guest tracking link may establish transaction-specific authority without Personal or Business Context. Platform Administration uses explicit internal authorization rather than Business membership.

## 2.2 Evaluation stages

| Stage | Question | Failure category | Typical safe experience |
|---|---|---|---|
| Identity/authority | Who or what authorizes this request? | Authentication required, expired bounded link | Sign in, verify, renew link, or safe public fallback |
| Active context | Where is the person acting? | Wrong/ambiguous context | Context chooser or explicit context switch |
| Applicability | Does this capability apply to this surface, Business, or resource type? | Not applicable | Omit routine entry or explain incompatibility where requested |
| Membership | Does the identity have an active relationship to this Business? | No membership, pending, suspended, removed | Safe denial, invitation outcome, or another context |
| Scope | Is the Business, Location, or assignment inside allowed scope? | Outside scope | Restricted state without scoped data leakage |
| Commercial Entitlement | Is the Business commercially allowed this plan/module/capability/quota? | Not entitled, quota exhausted, commercial suspension | Authorised commercial recovery; neutral unavailability for others |
| Module/capability state | Is the module enabled, configured, compatible, and available here? | Disabled, setup required, unavailable at Location | Enable/setup/status path for authorised users |
| Authorization | May this member perform this exact read or action? | Insufficient permission | Hidden routine entry, request access, or safe route denial |
| Resource/workflow policy | Is the resource actionable now, and are extra controls satisfied? | Read-only, approval, verification, state conflict, temporary restriction | Explain requirement and permitted next action |

## 2.3 Precedence rules

1. The active context and resource scope MUST be resolved before presenting Business-private data.
2. Membership and scope restrict the maximum domain in which permissions can operate.
3. Commercial Entitlement limits what the Business may use; it does not grant a person authority.
4. Module activation/configuration makes an entitled capability operational; it does not grant permission.
5. Permission operates only inside membership, scope, Entitlement, module, and resource constraints.
6. Approval or step-up verification does not replace permission; it is an additional requirement after permission exists.
7. When multiple gates fail, the experience presents the safest useful reason. It MUST NOT disclose a deeper private gate merely because it was evaluated.

## 2.4 Result categories

| Category | Meaning |
|---|---|
| Not applicable | Capability has no meaningful use in this Business/context/resource |
| Not entitled | Business lacks commercial rights or available quota |
| Module deactivated | Capability exists but is not operational; history may remain |
| Configuration required | Module is enabled but setup prevents operation |
| Wrong context/Location | Person may have authority elsewhere but not in the active scope |
| Insufficient permission | Relationship exists, but the exact action is not granted |
| Approval required | Person may initiate or request, but policy requires another authorized decision |
| Temporarily unavailable | A recoverable operational or external state blocks action |
| Suspended/restricted | Membership, Business, module, or policy state limits normal access |
| Forbidden | No safe actionable detail or recovery can be disclosed |

**Traceability:** Document 05 `CTX-009`, `NAV-007`–`NAV-011`, `LOC-011`, `MOD-001`–`MOD-006`.

---

# 3. Actor and Context Access Matrix

## 3.1 Matrix A — Actor/context to available surface

| Actor/context | Available surfaces | Context boundary | Typical access | Important restrictions/switching |
|---|---|---|---|---|
| Anonymous visitor | Marketing, Marketplace, published Business websites, permitted guest journeys | Public or bounded transaction | Public content and actions that do not require identity | No private Personal, Business, or Admin data |
| Authenticated consumer in Personal Context | Consumer account, Marketplace enhancements, Business websites, authorized personal activity | Cross-Business Personal Context; not a Business tenant | Own profile/activity and public/consented experiences | Merchant-owned records remain Business-isolated; Business ownership is an optional additional context |
| Primary Owner in Business Context | One active Business workspace plus permitted public previews | Exactly one active Business; Business-wide unless an approved restriction exists | Owner-only and delegated Business authority, constrained by Entitlement, module, and policy | Ownership-sensitive actions remain protected; other Businesses are evaluated separately |
| Manager in Business Context | Authorized Business workspace | One active Business and allowed Location scope | Broad delegated operations | No implied ownership, billing, entitlement purchase, transfer, closure, or unrestricted delegation |
| Member in Business Context | Permission-derived Business areas | One active Business and allowed Location scope | Explicitly granted reads/actions; templates may seed grants | Job title does not grant authority; no access outside grants/scope |
| Location-scoped Member | Permission-derived areas for allowed Locations | Selected Locations only | Same permission semantics, constrained to allowed Locations | “All Locations” means all allowed Locations; disallowed Locations remain private |
| Multi-Business operator | Personal Context and each authorized Business independently | One active Business at a time for Business routes | May hold different roles, templates, scopes, modules, and permissions per Business | No cross-Business inheritance or assumed module parity |
| Delivery Partner operating mode | Purpose-specific assigned-delivery surface | Business plus assignment scope | Minimum data/actions required for assigned delivery work | No general Business workspace or unrelated customer data |
| Platform Super Admin | Separate Platform Administration surface and explicit Business administrative work views | Platform Administration Context | Broad legitimate diagnosis, correction, configuration, and customization | Never silently attributed as Primary Owner; sensitive data remains minimized/redacted |
| Future developer | Future Developer surface only when introduced | Separate Developer Context | Future application/module scope | Deferred; no Business access except approved installation contracts |

**Traceability:** Document 05 `CTX-001`–`CTX-013`, `SUR-004`–`SUR-008`, Part 16, Part 17.

## 3.2 Context switching consequences

- Context switching changes the evaluated membership, scope, role, permissions, Entitlements, module states, and available resources.
- A stronger role in Business A has no effect in Business B.
- Personal Context remains available to owners and members.
- Admin authority is entered explicitly; it is not automatically active because the identity is an administrator.
- Direct links may select a valid context for that journey but never create authority.

---

# 4. Core Role Experience Matrix

## 4.1 Role, template, and customization

| Concept | Purpose | Experience consequence |
|---|---|---|
| Core role | Establish invariant Business authority posture | Primary Owner, Manager, or Member |
| Permission template | Reusable, named starting preset for a job function | Helps configure grants and landing emphasis; name itself grants nothing |
| Individual customization | Adjust one member’s permissions or scope | Effective access may differ from the selected template |
| Assignment-scoped mode | Bound work to assigned resources where the experience is fundamentally different | Delivery Partner uses a minimal purpose-specific surface |

## 4.2 Matrix C — Core role to default experience posture

| Core role | Default authority posture | Normally visible | Normally configurable | Normally restricted | Delegation |
|---|---|---|---|---|---|
| Primary Owner | Highest Business authority; exactly one per Business | Entitled/configurable Business areas, owner settings, access management, status/recovery | Business settings, memberships, templates, modules, billing/Entitlement controls where supported | Platform-only controls and policy-prohibited actions | May delegate within non-transferable ownership boundaries |
| Manager | Broad delegated operational authority | Operational areas and settings allowed by grants and Location scope | Delegated operational configuration and Member access where permitted | Ownership transfer, Business deletion/closure, owner security, commercial purchase by default, unrestricted manager creation | May grant only authority they are allowed to delegate; never beyond their own ceiling |
| Member | Least-assumption posture | Only granted capabilities and required context | Only explicitly granted configuration/actions | Ownership, billing, access administration, and ungranted modules/actions | None by default; may receive narrowly delegated access-management authority if canonically defined later |

These are default postures, not an exhaustive permission table. Exact action authority comes from canonical permissions. Commercial Entitlement and module state still apply to the Primary Owner.

## 4.3 Ownership-only action categories

The following are normally Primary-Owner-only unless a later canonical decision explicitly permits controlled delegation:

- ownership transfer;
- Business closure or deletion initiation;
- owner account/security recovery affecting Business control;
- final authority over Business billing and plan acceptance;
- appointment or removal of another Manager where this changes the delegation ceiling; and
- high-impact access-policy changes that could displace the Primary Owner.

Platform Super Admin may perform legitimate platform-level corrections through Admin Context; that is not delegated Business ownership.

**Traceability:** Document 05 `CTX-011`, Part 10, `JRN-OWN-001`; Document 04 Part 2 and §5.1 provide the legacy inventory being normalized.

---

# 5. Permission Template Experience

## 5.1 Template principles

Accountant, Receptionist, Doctor, Trainer, Cashier, Inventory Manager, and similar labels are configurable permission templates applied to a Member. They are not foundational roles.

**TEMPLATE-001:** The template name MUST NOT be presented as proof of authority.

**TEMPLATE-002:** Before assignment, the experience MUST summarize granted modules/capabilities, action level, Location scope, sensitive-data access, and notable restrictions.

**TEMPLATE-003:** Customized access MUST be visibly distinguishable from an unchanged template, for example “Based on Receptionist — customized.”

**TEMPLATE-004:** Effective access, not template label, controls navigation and actions.

## 5.2 Template lifecycle experience

| Step | Required experience |
|---|---|
| Select template | Show purpose, current grants, sensitive access, and restrictions in plain language |
| Customize before assignment | Allow authorized changes with a clear effective-access summary |
| Assign to member | Confirm core role, Business/Location scope, template, and custom changes together |
| Inspect member | Show inherited/preset values separately from member-specific overrides |
| Update template | Preview affected members and whether changes propagate under the eventual canonical policy |
| Detach/change template | Preserve an explicit summary of resulting grants; never silently broaden access |
| Compare templates | Compare meaningful capabilities and sensitive access, not job-title prestige |

## 5.3 Multiple functions

A Member may perform more than one job function. The experience MAY support combined templates only after the combination and precedence policy is canonical. Until then, authorized administrators should configure the final permission set explicitly.

Open semantics for template propagation, combination, and override precedence are recorded in Section 19 rather than invented here.

---

# 6. Navigation and Visibility Behavior

## 6.1 Visibility is an experience projection

Navigation is generated from effective access, but it is not enforcement. A route hidden from navigation remains independently protected.

## 6.2 Matrix D — Unavailability reason to visibility and next action

| Reason | Routine navigation | Direct route | Explanation | Next action |
|---|---|---|---|---|
| Allowed and relevant | Visible and enabled | Open | Usually none | Perform action |
| Allowed but read-only | Visible where useful | Open read-only | Explain why editing is unavailable | View, export if allowed, request change |
| Not applicable | Usually hidden | Safe parent or incompatibility explanation | Explain only when person intentionally requested it | Return to relevant area |
| Business not entitled | Discoverable to Primary Owner/authorized commercial user; usually hidden from routine Members | Layer-specific commercial state | Explain plan/capability gap without pricing invention | Review plan/request owner action |
| Module deactivated | Owner/authorized setup users may see status; routine operational entry removed | Deactivation/history state | Explain stopped operations and retained history | Re-enable if compatible |
| Configuration required | Visible to setup-authorized users; dependent Members may see “not ready” | Setup or not-ready state | Explain required setup safely | Configure or contact authorized person |
| Outside Location scope | Hidden from scoped navigation | Restricted state | “You do not have access to this Location” where safe | Choose allowed Location/request access |
| Insufficient permission | Hidden when existence is sensitive; otherwise disabled/requestable | Safe access denial | Explain permission category where safe | Request access/ask administrator |
| Approval required | Visible with pending/approval state | Open workflow state | Explain approver or requirement where safe | Submit, await, withdraw |
| Temporary operational failure | Visible with status | Status/retry state | Explain temporary condition | Retry, choose alternative, contact support |
| Suspended/restricted | Status/recovery entry only for authorized users | Restricted state | Explain policy/status at allowed disclosure level | Resolve, appeal, contact support |
| Forbidden/private existence | Hidden | Neutral denial or not-found-equivalent | Do not confirm resource existence | Safe context home |

## 6.3 Request-access behavior

Request access is appropriate only when:

- an authorized Business administrator can grant the access;
- the requested capability and scope can be described safely;
- the requester’s identity and Business relationship are known; and
- a request workflow exists.

The CTA MUST identify what is being requested and, where safe, who can decide. It MUST NOT promise approval.

**Traceability:** Document 05 §10.2, `NAV-007`–`NAV-012`, `MOD-006`, `DLK-006`.

---

# 7. Access-State UX Taxonomy

## 7.1 Matrix B — Access condition to experience state

| Experience state | What the person sees | Explain reason? | Available actions | Audit expectation |
|---|---|---|---|---|
| Allowed | Full permitted experience | No, unless scope is important | Normal actions | Sensitive writes follow domain audit |
| Read-only | Data with editing removed/disabled | Yes, where useful | View, permitted export, request access | Sensitive reads may require security logging |
| Disabled | Known action unavailable due to current state | Yes | Resolve state or alternative | Log consequential attempts where useful |
| Hidden | No routine navigation or control | No | None | Enforcement still logs prohibited attempts as policy requires |
| Request access | Restricted summary and request CTA | Yes | Submit/cancel request | Request and decision attributable |
| Approval required | Pending/required approval state | Yes | Submit, review status, withdraw if allowed | Full decision attribution |
| Upgrade/Entitlement required | Commercially unavailable state | Yes to authorized commercial users; neutral to others | Review plan, contact Primary Owner/admin | Commercial change audited |
| Module enablement required | Module not active | Yes to authorized users | Enable, configure, or contact authorized user | Activation/configuration audited |
| Configuration required | Setup incomplete or invalid | Yes | Complete setup or contact setup owner | Consequential configuration audited |
| Wrong Location/context | Current scope is incompatible | Yes without leaking data | Switch to allowed context/Location | Repeated denied access may be security logged |
| Suspended/restricted | Limited status and recovery | Yes at permitted disclosure level | Resolve/appeal/support | State change and sensitive attempts audited |
| Forbidden | Neutral terminal denial | Minimal | Safe exit | Security logging as required |

## 7.2 State composition

More than one state may apply. The experience presents one primary reason and may show secondary requirements only after the person is authorized to know them.

Example: a Member lacking permission to a commercially unavailable module should not receive an upgrade pitch merely because the Business also lacks Entitlement. A Primary Owner may receive the commercial recovery state.

---

# 8. Location-Scoped Access Experience

## 8.1 Scope model

A Business membership is either:

- **Business-wide:** permissions may operate across all Locations, subject to module/resource rules; or
- **Selected-Location:** permissions operate only within explicitly allowed Locations.

A permission never expands Location scope.

## 8.2 Location behavior

**SCOPE-001:** The Location switcher lists only allowed Locations.

**SCOPE-002:** “All Locations” means all Locations within the member’s allowed scope. The interface MUST label whether a view is Business-wide, all-allowed, or one-Location.

**SCOPE-003:** Business-wide summaries MUST omit unauthorized Locations. Totals MUST NOT allow inference of excluded Location data.

**SCOPE-004:** A direct link to a disallowed Location returns a restricted state without silently substituting a different Location or exposing the target resource.

**SCOPE-005:** Location-aware navigation appears only for allowed Locations where the module/capability is available.

**SCOPE-006:** A module’s Business-level activation does not guarantee availability or configuration at every Location.

## 8.3 Scope changes

When Location access is added:

- newly available Locations appear after re-evaluation;
- the current page may offer an explicit switch if the resource exists there; and
- no default Location is changed silently unless the previous default became invalid.

When Location access is removed:

- protected reads/writes fail immediately on the next enforcement point;
- the removed Location disappears from switchers and navigation;
- open pages transition to the nearest safe authorized state;
- cached private content is cleared according to security policy; and
- the person is told that their Location access changed where safe.

**Traceability:** Document 05 `CTX-012`, Part 11, `LOC-008`–`LOC-011`, `JRN-LOC-002`, `JRN-LOC-003`.

---

# 9. Multi-Business Access Experience

## 9.1 Independent evaluation

Every Business Context is evaluated independently. The same Platform Identity may be:

- Primary Owner in Business A;
- Manager with selected-Location access in Business B; and
- Member using a customized Accountant template in Business C.

No role, template, permission, Location scope, module state, or Commercial Entitlement carries across Businesses.

## 9.2 Switching behavior

On Business switch, the platform MUST re-evaluate:

1. membership and membership state;
2. allowed Location scope;
3. core role and effective permissions;
4. Commercial Entitlements;
5. enabled/configured modules;
6. Business, Location, and resource states; and
7. the valid landing destination.

An equivalent route may be offered only when it exists and is authorized in the target Business. Otherwise, route to the target Business’s permission-derived home.

Unsaved work must be resolved before switching. The route identifies the active Business; remembered context never grants access.

**Traceability:** Document 05 `NAV-001`–`NAV-005`, `CTX-004`, `CTX-009`, `JRN-BIZ-003`.

---

# 10. Invitation and Membership Access Lifecycle

## 10.1 Lifecycle states

| State | Invitee/member experience | Existing access | Administrator experience |
|---|---|---|---|
| Invitation created | No access until sent and accepted | None | Review target, core role, template, grants, Location scope, expiry |
| Invitation sent/pending | Safe preview after link validation; authenticate to continue | None | Resend/revoke where allowed; see pending state |
| Invitation accepted | Explicitly enter target Business with effective-access summary | Begins after acceptance and validation | See active membership and attributable acceptance |
| Invitation expired | Explain expiry without private disclosure | None | Resend/create replacement |
| Invitation revoked | Safe unavailable state | None | Revocation recorded |
| Member active | Permission-derived workspace | Normal evaluated access | Manage within delegation authority |
| Access changed | Explain material change where safe | Re-evaluated immediately | Preview and confirm consequential impact |
| Member suspended | Restricted/status experience | New protected operations blocked | Reinstate/remove according to authority |
| Member removed | Exit Business Context | Revoked; prior actions retained in audit/history | Removal confirmation and attribution |

## 10.2 Invitation review

Before acceptance, the invitee should understand:

- Business identity;
- inviter;
- core role;
- selected-Location or Business-wide scope;
- template or meaningful access summary;
- notable sensitive access;
- expiry; and
- what accepting will add to their existing Platform Identity.

The preview MUST not expose private Business data before authority is established.

## 10.3 Session consequences

Membership suspension or removal takes effect at the next protected read/write without requiring sign-out. Open tabs do not preserve authority. Notifications and deep links targeting the removed context resolve to a safe changed-access state.

**Traceability:** Document 05 `JRN-MEM-001`–`JRN-MEM-004`, `JRN-MEM-008`, `RT-INV-001`, §10.4.

---

# 11. Permission-Change Experience

## 11.1 Change principles

**CHANGE-001:** Access changes are enforced immediately at protected boundaries; UI refresh follows as soon as practical.

**CHANGE-002:** Granting access does not silently navigate a person away from current work. Newly available navigation appears after re-evaluation.

**CHANGE-003:** Revoking access removes affected actions/navigation and safely exits any now-invalid route.

**CHANGE-004:** Current forms MUST fail safely at submission if authority changed after page load. They MUST NOT save through stale permission.

**CHANGE-005:** Material access changes identify what changed, who changed it where appropriate, and what the member can do next.

## 11.2 Matrix E — Scope/change to expected behavior

| Change | Current open page | Navigation | Deep links | Communication |
|---|---|---|---|---|
| Permission granted | Remains stable; optional refresh notice | Add newly relevant destinations | Newly valid after recheck | Notify when useful/sensitive |
| Permission revoked | Allow no further protected action; exit if route invalid | Remove destinations | Safe denial | Explain changed access |
| Location added | Keep current scope | Add Location and relevant areas | Valid after recheck | Optional notification |
| Location removed | Exit affected resource/scope | Remove Location-derived entries | Restricted state | Explain Location access change |
| Module activated | Setup/operational entry appears according to permission | Add relevant contributions | Resolve to setup or active route | Notify affected operators if useful |
| Module deactivated | Stop new operations; preserve authorized history | Remove routine operational entry | Status/history or safe parent | Explain operational effect |
| Entitlement gained | Does not auto-grant permission or activation | Commercial/setup entry for authorized users | Re-evaluate other gates | Notify commercial authority |
| Entitlement lost/suspended | Stop gated operation according to policy | Recovery/status for authorized users | Layer-specific state | Notify affected authority and operators appropriately |
| Membership suspended/removed | Exit Business Context | Remove Business or mark unavailable as appropriate | Safe changed-access state | Notify member where policy permits |

---

# 12. Sensitive Actions

## 12.1 Categories

Stronger treatment may be proportionate for:

- ownership transfer;
- Business closure/deletion and permanent data deletion;
- member removal or major permission escalation;
- Location-scope expansion into sensitive operations;
- billing, payout, tax, payment, or financial configuration;
- export or bulk access to sensitive customer data;
- security, authentication, recovery, domain, and integration credentials;
- destructive or irreversible module/data actions;
- platform suspension, verification override, trust/safety action, or commercial correction.

## 12.2 Proportionate controls

| Control | Use when |
|---|---|
| Re-authentication/step-up | Identity assurance must be fresh for a high-risk action |
| Clear confirmation | Consequences are significant but the actor already has authority |
| Typed or explicit irreversible warning | Recovery is impossible or materially limited |
| Reason entry | Administrative, exceptional, or policy-sensitive change needs attribution |
| Second approval | Separation of duties is genuinely required; not a default startup-stage burden |
| Delayed execution/cancellation window | Risk is reduced by time to detect mistakes |
| Audit attribution | Action changes authority, sensitive configuration, commercial state, or platform policy |

Controls MUST be proportional. Routine operational edits should not inherit enterprise-grade ceremony merely because stronger controls exist elsewhere.

---

# 13. Platform Super Admin Access Experience

## 13.1 Current-stage authority

The founder-level Platform Super Admin has broad legitimate operational authority to:

- diagnose Business and platform issues;
- repair configuration;
- configure or correct module state;
- modify Business settings;
- customize Business websites, layouts, colours, content, and configuration;
- perform custom work not yet available through self-service;
- correct platform problems; and
- perform legitimate backend/platform administration.

## 13.2 Context and attribution

**ADMIN-ACCESS-001:** Super Admin authority is used only in explicit Platform Administration Context or a visibly administrative Business work scope.

**ADMIN-ACCESS-002:** Opening a Business from Admin does not create or simulate ordinary Business membership.

**ADMIN-ACCESS-003:** Mutations are attributed to “Platform Super Admin” and the acting Platform Identity, not falsely to the Primary Owner.

**ADMIN-ACCESS-004:** The Admin experience identifies the target Business, elevated context, action consequence, and reason requirement where appropriate.

**ADMIN-ACCESS-005:** A Business-rendered diagnostic view remains visibly administrative. Silent impersonation is prohibited.

**ADMIN-ACCESS-006:** Super Admin actions MUST change the correct layer. Configuring a module is not the same as granting Commercial Entitlement; changing Entitlement is not the same as granting a member permission.

## 13.3 Entry, Business work, and exit

`Explicit Admin entry → select issue/Business → inspect evidence → enter administrative work scope → perform attributed action → confirm/audit outcome → return to Admin work item → explicit exit`

Leaving Admin Context returns to a prior valid normal context or Personal Context. Elevation does not persist invisibly.

## 13.4 Future path

Future internal roles may introduce area grants, least privilege, time-bound elevation, case-scoped access, or additional approvals. This document does not require those structures for the current one-founder model.

**Traceability:** Document 05 `ADM-001`–`ADM-012`, `JRN-ADM-001`–`JRN-ADM-005`, `RT-ADM-001`–`RT-ADM-003`.

---

# 14. Access-Denied and Restricted-State Language

## 14.1 Copy principles

Access language should be:

- specific about the safe category;
- concise and direct;
- non-accusatory;
- explicit about the smallest valid next action;
- consistent with the active surface; and
- silent about private resources or controls the person is not authorized to know.

## 14.2 Examples

| Category | Example |
|---|---|
| Location scope | “You do not have access to this Location. Choose an available Location or ask a Business administrator for access.” |
| Permission | “You can view this area, but you cannot make changes. Ask a Business administrator if your access should be updated.” |
| Module state | “This capability is not enabled for this Business.” |
| Configuration | “Bookings are enabled, but setup is not complete.” |
| Entitlement | “This capability is not included in the Business’s current plan.” |
| Approval | “Additional approval is required before this change can be applied.” |
| Changed access | “Your access changed while this page was open. No changes were saved.” |
| Private/forbidden | “This page is unavailable.” |

Do not default every failure to “Permission denied.” Do not expose another member’s permissions, hidden Business existence, excluded Location totals, security policy, or private resource identifiers.

---

# 15. Deep Links and Route Guards

Document 05 remains authoritative for route families and Destination Intent. This section defines access outcomes after route resolution.

| Direct destination | Guarded outcome |
|---|---|
| Business with no active membership | Neutral denial or accessible Business chooser; do not reveal private Business data |
| Location outside membership scope | Location-restricted state; do not substitute another Location silently |
| Deactivated module | Authorized status/history or re-enable path; routine Members receive safe unavailable state |
| Capability not entitled | Commercial recovery for authorized users; neutral unavailability for others |
| Page without required permission | Read-only, request-access, or safe denial according to disclosure rules |
| Resource deleted/no longer available | Safe not-found/unavailable state and authorized parent |
| Membership/context changed | Re-evaluate, explain changed access, and route to nearest safe context |
| Invitation expired/revoked/mismatched | Safe invitation outcome without Business-private disclosure |

Route guards MUST run even when navigation omitted the destination. Client-side hiding, disabled buttons, and remembered context are never sufficient enforcement.

**Traceability:** Document 05 `DLK-001`–`DLK-008`, `CTX-009`, `LOC-010`, `MOD-006`, `RT-BIZ-004`–`RT-BIZ-007`.

---

# 16. Audit and Attribution Expectations

## 16.1 Actions generally requiring attribution

- invitation creation, resend, revocation, and acceptance;
- membership activation, suspension, removal, and restoration;
- core-role changes;
- permission-template assignment and customization;
- sensitive permission grants/revocations;
- Location-scope changes;
- ownership transfer;
- module activation/deactivation and consequential configuration;
- Commercial Entitlement or quota corrections;
- sensitive exports, security changes, and destructive actions; and
- Platform Super Admin investigation, configuration, customization, and policy actions.

## 16.2 Three evidence audiences

| Evidence type | Purpose | User visibility |
|---|---|---|
| User-facing activity history | Help authorized people understand meaningful Business/account changes | Human-readable, scoped, privacy-safe |
| Operational logs | Diagnose reliability and support issues | Internal, access-controlled |
| Security/legal audit evidence | Prove actor, authority, target, reason, before/after, time, and outcome | Restricted, tamper-resistant implementation deferred |

This document does not prescribe the audit database. It requires that consequential actions be attributable at the experience and domain-contract level.

---

# 17. Consolidated Canonical Matrices

The detailed matrices above are canonical. This section provides the compact implementation index requested by later specifications.

| Matrix | Canonical location | Governing question |
|---|---|---|
| Matrix A — Actor/context → available surface | §3.1 | Where may this identity act? |
| Matrix B — Access condition → experience state | §7.1 | What state should the interface render? |
| Matrix C — Core role → default experience posture | §4.2 | What authority posture does the role establish? |
| Matrix D — Unavailability reason → visibility/next action | §6.2 | Should the capability be visible, disabled, requestable, or hidden? |
| Matrix E — Scope change → expected behavior | §11.2 | What happens when access changes during use? |

These matrices deliberately do not reproduce a fake-complete per-feature permission table. Document 04 §2.13 remains the current action inventory, subject to the role and entitlement corrections recorded here.

---

# 18. Traceability

## 18.1 Primary source references

| Topic | Canonical reference |
|---|---|
| Kernel membership and grants | Document 03 §1.8, §5.1–§5.3 |
| Server-side/RLS enforcement | Document 03 §5.2 and Engineering Principles 22, 23, 33 |
| Current product role/action inventory | Document 04 Part 2, especially §2.1–§2.13 |
| Permission-template examples | Document 04 §2.8 and Staff/Team inventory, normalized by Document 05 `CTX-011` |
| Settings authority inventory | Document 04 §8.2 |
| Context and per-route evaluation | Document 05 `CTX-001`–`CTX-013` |
| Access-sensitive navigation | Document 05 `NAV-007`–`NAV-012` |
| Role/template experience | Document 05 Part 10 |
| Location scope | Document 05 Part 11, `LOC-008`–`LOC-011` |
| Entitlement/module layers | Document 05 Part 12, `MOD-001`–`MOD-009` |
| Membership journeys | Document 05 `JRN-MEM-001`–`JRN-MEM-008`, `JRN-OWN-001` |
| Admin experience | Document 05 Part 16, `ADM-001`–`ADM-012` |
| Business/admin routes | Document 05 `RT-BIZ-004`–`RT-BIZ-007`, `RT-DEL-001`, `RT-ADM-001`–`RT-ADM-003` |

## 18.2 Traceability limitations

Documents 03 and 04 do not provide stable IDs for most individual permissions. Document 04 contains the richest existing inventory, but only some modules define explicit permission blocks and its role vocabulary predates the approved role/template model.

Therefore:

- section references are used where stable IDs do not exist;
- Document 04 §2.13 is a baseline inventory, not a complete final permission contract;
- no exhaustive action catalogue is implied by this document; and
- later permission and technical specifications must introduce stable permission identifiers before final API/database design.

---

# 19. Conflict, Gap and Decision Register

## 19.1 Genuine cross-document conflicts

| ID | Conflict | Governing resolution | Severity |
|---|---|---|---|
| `RPA-CONFLICT-001` | Document 03 uses owner/manager/staff/delivery-partner roles; Document 04 adds Accountant and Receptionist as roles | Primary Owner, Manager, and Member are invariant roles; job functions are configurable templates; Delivery Partner remains assignment-scoped pending final Kernel shape | Blocking before permission schema |
| `RPA-CONFLICT-002` | Document 04 says Primary Owner sees all navigation | Authority does not require permanent visibility; progressive, relevant, module/state-aware navigation governs | Important, non-blocking |
| `RPA-CONFLICT-003` | Document 04 includes Admin “Impersonate” | Use explicit attributed Platform Super Admin work/diagnostic context; no silent Owner attribution | Blocking before Admin security/API design |
| `RPA-CONFLICT-004` | Document 03 `manage` combines configuration/uninstall while approved architecture separates Entitlement, activation, configuration, and deactivation | Define separate canonical actions/layers; operational removal is deactivation with retained history | Blocking before permission/module contracts |
| `RPA-CONFLICT-005` | Document 03 capability computation omits Commercial Entitlement and Location availability | Entitlement and contextual availability are first-class inputs before person authorization | Blocking before capability/API design |
| `RPA-CONFLICT-006` | Document 04 permits Admin module installation while also assigning sole billing/plan authority to Owner | Super Admin may correct/configure through attributed Admin authority; commercial grant and Business purchase remain distinct operations | Important; exact commercial correction policy unresolved |

## 19.2 Missing concepts and semantics

| ID | Gap | Required follow-up | Severity |
|---|---|---|---|
| `RPA-GAP-001` | Kernel lacks configurable permission-template semantics | Amend role/membership contract under Document 05 `KIR-001` | Blocking |
| `RPA-GAP-002` | Kernel lacks Business-wide vs selected-Location membership grants | Add Location scope semantics under `KIR-004` without creating Location tenants | Blocking |
| `RPA-GAP-003` | Kernel capability model lacks Commercial Entitlement | Add kernel-consumed Entitlement contract under `KIR-005` | Blocking |
| `RPA-GAP-004` | Exact permission granularity is incomplete beyond coarse module read/write/manage and selected product actions | Create canonical permission catalogue before final data/API authorization design | Blocking |
| `RPA-GAP-005` | Manager delegation ceiling is not sufficiently defined across permissions, templates, and Location scope | Define what Managers may grant, revoke, and assign | Blocking |
| `RPA-GAP-006` | Template propagation, combination, and override precedence are undefined | Resolve in permission semantics specification | Important, non-blocking for page architecture |
| `RPA-GAP-007` | Membership suspension semantics are not aligned across Kernel and product lifecycle inventory | Define canonical states and enforcement consequences | Blocking before membership schema/API |
| `RPA-GAP-008` | Approval requirements exist as a UX category but no general approval authority model is canonical | Define only for workflows that genuinely need approval | Deferred until workflow inventory requires it |
| `RPA-GAP-009` | Future internal Admin roles and elevation policy are not defined | Defer; current founder Super Admin model is sufficient | Deferred |
| `RPA-GAP-010` | Stable permission identifiers are absent from Documents 03 and 04 | Introduce identifiers in the future canonical permission/technical contract | Blocking before final API contracts |

## 19.3 Unresolved access decisions

| ID | Decision | Recommendation | Blocks |
|---|---|---|---|
| `RPA-DEC-001` | Canonical action vocabulary and granularity: module-level read/write/manage versus capability/action permissions | Use stable capability/action permissions with module-level presets as convenience, not the sole enforcement model | Physical permission schema and APIs |
| `RPA-DEC-002` | Exact Manager delegation ceiling | Managers may grant only delegable permissions within their own authority and Location scope; owner-sensitive grants remain prohibited | Permission management pages, schema, APIs |
| `RPA-DEC-003` | Whether template updates propagate automatically, require opt-in, or create versions | Prefer versioned templates with impact preview and explicit propagation | Template data model and update UX |
| `RPA-DEC-004` | Multiple-template merge and deny precedence | Prefer an explicit computed preview with scope/deny taking precedence; formal semantics still required | Template combination and evaluator |
| `RPA-DEC-005` | Delivery Partner representation as separate role enum or assignment-scoped Member mode | Preserve the distinct operating experience; decide domain representation in Kernel amendment | Final membership schema |
| `RPA-DEC-006` | Which Commercial Entitlement changes Super Admin may make without Primary Owner acceptance | Permit attributable corrections and support grants; define boundaries for purchases, contractual acceptance, and lasting plan changes | Billing/Admin API design, not page architecture |

## 19.4 Blocking summary

Before physical database or authorization API design, resolve:

1. the Kernel role/template model;
2. Location-scoped membership semantics;
3. Commercial Entitlement input and authority;
4. canonical permission identifiers and granularity;
5. Manager delegation limits;
6. membership suspension lifecycle; and
7. Delivery Partner domain representation.

These decisions do not block the next page-by-page experience specification when pages cite the access states and mark unresolved permission identifiers explicitly.

---

# Document Completion Criteria

This document is stable when later page specifications can determine:

1. which access gates apply;
2. how core role, template, customization, and scope differ;
3. what navigation and route behavior follows each unavailability reason;
4. how access changes affect open experiences;
5. how sensitive and administrative actions are attributed;
6. what must be explained or concealed; and
7. which unresolved permission semantics belong to Kernel/data/API design.

---

**End of Document 06 — Role, Permission & Access Experience Matrix**
