Immediate Priorities — Performance, Razorpay Connect, Cleanup
Work Order for Claude Code
Three things, in this order. This is separate from and comes before the design work order (Prompts A/B) — get it fast and functionally complete first, then make it look right.
1. Performance diagnosis (do this first — don't guess, measure)
The person testing this reports every click taking ~10 seconds. Before changing anything, find the real cause:

1. Run `pnpm build && pnpm start` for the workspace app instead of `pnpm dev`, and time the same clicks. If it's dramatically faster, the dev-mode compilation theory is confirmed — note this clearly, since it means nothing is actually broken, just that dev mode was never representative.
2. Independent of #1: pick 3 slow-feeling Workspace pages and measure where time actually goes — server-render time, number of sequential vs parallel API calls per page load, and per-query latency against the hosted DB (ap-northeast-1). Use the correlation_id logging already built (AUD-11) to see real request timing.
3. Check whether any Workspace page fires N+1 or sequential-awaited fetches that could be parallelized with Promise.all / concurrent async calls.
4. Report findings with numbers, not impressions. Fix what's actually slow. Do not propose an infrastructure change (different DB, different region, different hosting) without first proving dev-mode + query-pattern explanations don't account for it.

2. Razorpay connect flow (real UI, no key work needed from you yet)
The Payments page currently only displays merchant connection status — there is no form to actually enter credentials. Build:

* A "Connect Razorpay" form on the Payments page (or a dedicated sub-page) where the owner pastes their Razorpay Key ID and Key Secret (obtained from their own Razorpay dashboard, after their own KYC with Razorpay — this platform is not replicating Razorpay's onboarding, just storing the credentials).
* Save to `MerchantConnection`, encrypted at rest if not already (check the existing model — this is API secret material, treat it accordingly, same discipline as everything logged/redacted in AUD-11).
* A "Test connection" action that makes one real, safe Razorpay API call (e.g. fetch account details) to confirm the keys work before marking the connection `active`.
* Clear status states: not connected / connected but unverified / active / invalid credentials — reusing the GateNotice-style pattern already established elsewhere.
* Do not build actual payment processing yet — that's separate, larger work once real keys exist and this UI is confirmed working. This is just "can an owner get their credentials into the system at all."

3. Location cleanup — check before fixing
Investigate the duplicate "Chennai" rows shown in the Locations page for this test business. Determine: is this leftover test data from the earlier manual walkthrough (someone/something called "Add location" twice), or a real bug where location creation duplicates? Report which, and if it's a real bug, fix it. If it's just test data, delete the duplicate for this one business (same founder-authorized cleanup pattern as before) and move on.
Report all three with real evidence — the performance numbers, a screenshot or description of the working Razorpay form, and the location finding.
