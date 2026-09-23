"""Natural-language intent is advisory; only platform registries grant meaning."""

from __future__ import annotations

import re

from platform_core.business_type_profiles.registry import BusinessTypeProfileRegistry
from platform_core.entitlements.capability_registry import CAPABILITIES
from platform_core.entitlements.models import ResolvedEntitlement
from platform_core.entitlements.module_registry import ModuleRegistry
from platform_core.entitlements.resolver import PlatformCapabilityResolver
from platform_core.interview.models import (
    BusinessBlueprint,
    CapabilityGapProposal,
    CapabilityIntent,
    Message,
    ModuleRecommendation,
)

# Recommendation vocabulary, not business-type mechanics. Every value is verified
# against the canonical registry below; registry presence alone is not availability.
INTENTS = {
    "catalog": (
        "offerings-catalog",
        "Show your products or services",
        r"\b(products?|catalog(?:ue)?|menu|services?|browse)\b",
    ),
    "orders": ("orders", "Take orders online", r"\b(orders?|buy|purchase|checkout|pre-?order)\b"),
    "bookings": (
        "bookings",
        "Take bookings and appointments",
        r"\b(book|bookings?|appointments?|reservations?|reserve)\b",
    ),
    "enquiries": ("leads", "Receive enquiries", r"\b(enquir\w*|inquir\w*|contact us|call us|whatsapp)\b"),
    "quotes": (
        "quotes",
        "Send quotations",
        r"\b(quotes?|quotations?|estimates?|rfq|request (?:a |for )?(?:price|quote))\b",
    ),
    "memberships": ("memberships", "Run memberships and subscriptions", r"\b(memberships?|subscriptions?|monthly plans?)\b"),
    "payments": ("payments", "Collect payments online", r"\b(payments?|pay online|upi)\b"),
    "inventory": ("inventory", "Keep track of stock", r"\b(inventory|stock)\b"),
    "delivery": ("fulfilment", "Manage delivery and pickup", r"\b(deliver\w*|pickup|pick up|fulfilment)\b"),
    "projects": ("projects", "Track projects and work orders", r"\b(projects?|work orders?|installations?)\b"),
    "reviews": ("reviews", "Collect customer reviews", r"\b(reviews?|feedback|ratings?)\b"),
    "messaging": ("messaging", "Message customers", r"\b(messag\w+|sms|broadcasts?)\b"),
    "crm": ("customer-relationships", "Keep customer records", r"\b(customer (?:records|list|history)|crm)\b"),
    "loyalty": ("loyalty", "Reward repeat customers", r"\b(loyalty|rewards?|points)\b"),
    "invoicing": ("invoicing", "Send invoices", r"\b(invoices?|invoicing|bills?|gst bill)\b"),
}
LABELS = {module: label for module, label, _ in INTENTS.values()}
CUSTOMER_FACING = frozenset(
    {"offerings-catalog", "orders", "bookings", "leads", "quotes", "memberships",
     "payments", "fulfilment", "reviews", "loyalty"}
)

# Classification aliases extend registry data; never grant tools or branch workflow.
CLASSIFICATION_SEEDS = {
    "hospital": "clinic",
    "medical": "clinic",
    "furniture": "retail",
    "meat shop": "retail",
    "clothing": "retail",
    "product seller": "retail",
    "home food": "restaurant",
    "home-food": "restaurant",
    "real estate": "professional_service",
    "professional services": "professional_service",
}


def blueprint_text(bp: BusinessBlueprint) -> str:
    """Everything the owner has actually said, as one lowercase haystack.

    Extraction assigns each field one exact quotation from a much longer answer,
    so the sentence that happens to land in `description` is not reliably the
    sentence that says what the business is. A hospital that described itself in
    one paragraph had "we run a 24 hour emergency department" as its description
    and the word "hospital" only in its name and its offerings — and reading two
    fields classified it as "other", which then chose its template and its whole
    website. What the owner said is what they said, wherever it was filed.
    """
    facts = {**bp.known_facts, **bp.unconfirmed_facts}
    parts = [fact.value for fact in facts.values()]
    parts += [fact.value for fact in bp.identity.values()]
    parts += [intent.original_request for intent in bp.requested_capabilities]
    return " ".join(parts).lower()


def because(said: str) -> str:
    """Why a tool is recommended, in the owner's own words."""
    quote = " ".join(said.split()).strip(" .")
    if len(quote) > 110:
        quote = quote[:107].rsplit(" ", 1)[0] + "…"
    return f"Because you said “{quote}”."


def classification_seed(bp: BusinessBlueprint) -> str:
    text = blueprint_text(bp)
    candidates = {
        **CLASSIFICATION_SEEDS,
        **{
            row["type_id"].replace("_", " "): row["type_id"]
            for row in BusinessTypeProfileRegistry.list_types()
        },
    }
    for phrase, seed in candidates.items():
        if re.search(r"\b" + re.escape(phrase) + r"\b", text):
            return str(seed)
    return "other"


def resolve_recommendations(bp: BusinessBlueprint, entitlement: ResolvedEntitlement) -> None:
    snapshot = PlatformCapabilityResolver.resolve_from_entitlement(entitlement)
    facts = {**bp.known_facts, **bp.unconfirmed_facts}
    action = facts.get("customer_actions")
    requests = list(bp.requested_capabilities)
    if action:
        # Deterministic fallback recommendations, only from an explicit desired action.
        for intent, (_, _, pattern) in INTENTS.items():
            if re.search(pattern, action.value, re.I) and not re.search(
                r"\b(no|not|don't|without)\b", action.value, re.I
            ):
                requests.append(CapabilityIntent(intent=intent, original_request=action.value))
    # An unsupported ask must be answered wherever the owner happened to say it,
    # and whether or not extraction kept it. A hospital asked for "live GPS
    # tracking of our ambulances" in the same breath as everything else;
    # extraction has no field for it, so the sentence was dropped, nothing was
    # raised, and the request passed in silence — which reads to the owner as
    # the platform having quietly agreed to build it. Confirmed facts are
    # checked first, then the owner's own words.
    spoken = [fact.value for fact in facts.values()]
    spoken += [message.text for message in bp.messages if message.role == "user"]
    tracking = re.compile(
        r"[^.!?]*\b(?:live\s+\w*\s*track\w*|track\w*\s+live|courier[^.!?]*map|gps)\b[^.!?]*",
        re.I,
    )
    for said in spoken:
        match = tracking.search(said)
        if match:
            requests.append(
                CapabilityIntent(
                    intent="live_courier_tracking",
                    original_request=(match.group(0).strip() or said)[:4000],
                )
            )
            break
    wanted: dict[str, str] = {}
    gaps: dict[str, CapabilityGapProposal] = {}
    for request in requests:
        if request.intent not in INTENTS:
            gaps[request.intent] = CapabilityGapProposal(
                original_request=request.original_request,
                normalized_intent=request.intent,
                business_classification=classification_seed(bp),
                closest_supported_capabilities=["use_fulfilment"]
                if "track" in request.intent
                else [],
                why_unsupported="This specific workflow is not available in the current platform. It will not be added to your website.",
                required_mechanics=[
                    "A separately designed, authorised and tested platform integration"
                ],
                session_reference=bp.session_id,
            )
            continue
        module, _, _ = INTENTS[request.intent]
        if ModuleRegistry.get(module) and module not in wanted:
            wanted[module] = because(request.original_request)

    def dependencies(module: str) -> None:
        definition = ModuleRegistry.get_or_raise(module)
        for dep in definition.dependencies:
            if dep in ModuleRegistry.platform_core_ids() or dep in wanted:
                continue
            wanted[dep] = (
                f"Needed by {LABELS.get(module, definition.display_name).lower()}; your choice is still required."
            )
            dependencies(dep)

    for module in list(wanted):
        dependencies(module)
    recommendations = []
    for module, reason in wanted.items():
        definition = ModuleRegistry.get_or_raise(module)
        state = entitlement.module_states.get(module)
        caps = [key for key, cap in CAPABILITIES.items() if cap.required_module_id == module]
        enabled_features = all(
            entitlement.feature_states.get(feature) and entitlement.feature_states[feature].enabled
            for feature in definition.features[:1]
        )
        if not state or not state.entitled or not enabled_features:
            status = "NOT_CURRENTLY_AVAILABLE"
            why = "Not included or enabled in your current access. Choosing this does not upgrade your plan."
        elif state.activation_state != "active":
            status = "SUPPORTED_NOT_ENABLED"
            why = "Off. Your approval can enable it; setup is still required before customers can use it."
        elif (
            not state.configuration_ready
            or not state.dependency_satisfied
            or any(not snapshot.capabilities.get(cap, False) for cap in caps)
        ):
            status = "SUPPORTED_REQUIRES_CONFIGURATION"
            why = "Requires setup, dependencies or available usage allowance."
        else:
            status = "SUPPORTED"
            why = "Enabled. Actual products, availability and payment configuration still govern customer actions."
        recommendations.append(
            ModuleRecommendation(
                module_id=module,
                label=LABELS.get(module, definition.display_name),
                reason=reason,
                capability_ids=caps,
                dependencies=list(definition.dependencies),
                status=status,
                availability_reason=why,
                choice="declined"
                if module in bp.declined_modules
                else "approved"
                if module in bp.approved_modules
                else "pending",
            )
        )
    bp.recommended_modules = recommendations
    bp.unsupported_requests = list(gaps.values())[:40]


def available_modules(
    bp: BusinessBlueprint, entitlement: ResolvedEntitlement
) -> list[ModuleRecommendation]:
    """Every optional tool this business could switch on, straight from the registry.

    Available is not recommended, and neither is active. A tool appears here
    because the platform supports it and the business is entitled to it — a
    module added to the registry tomorrow appears here without a code change.
    Recommendation needs evidence from the conversation and lives elsewhere.
    """
    recommended = {item.module_id for item in bp.recommended_modules}
    snapshot = PlatformCapabilityResolver.resolve_from_entitlement(entitlement)
    result: list[ModuleRecommendation] = []
    rows = sorted(
        ModuleRegistry.list_modules(),
        key=lambda row: (row["module_id"] not in CUSTOMER_FACING, row.get("display_name") or ""),
    )
    for row in rows:
        module = row["module_id"]
        if row.get("module_class") != "optional" or module in recommended:
            continue
        definition = ModuleRegistry.get(module)
        state = entitlement.module_states.get(module)
        if not definition or not state or not state.entitled:
            continue
        if definition.features and not all(
            entitlement.feature_states.get(feature)
            and entitlement.feature_states[feature].enabled
            for feature in definition.features[:1]
        ):
            continue
        caps = [key for key, cap in CAPABILITIES.items() if cap.required_module_id == module]
        if state.activation_state != "active":
            status = "SUPPORTED_NOT_ENABLED"
            why = "Available with your current access. Your approval is needed before it can be enabled."
        elif (
            not state.configuration_ready
            or not state.dependency_satisfied
            or any(not snapshot.capabilities.get(cap, False) for cap in caps)
        ):
            status = "SUPPORTED_REQUIRES_CONFIGURATION"
            why = "Available with your current access, but setup or a prerequisite is still needed."
        else:
            status = "SUPPORTED"
            why = "Already switched on."
        result.append(
            ModuleRecommendation(
                module_id=module,
                label=LABELS.get(module, definition.display_name),
                reason=getattr(definition, "description", "") or definition.display_name,
                capability_ids=caps,
                dependencies=list(definition.dependencies),
                status=status,
                availability_reason=why,
                group="customer" if module in CUSTOMER_FACING else "operations",
                choice="declined"
                if module in bp.declined_modules
                else "approved"
                if module in bp.approved_modules
                else "pending",
            )
        )
    return result


def surface_new_unsupported_requests(
    bp: BusinessBlueprint, previous_intents: set[str]
) -> None:
    """Put a newly detected capability gap into the authoritative reply.

    Capability resolution happens after extraction, so the orchestrator's next
    question cannot mention a gap that did not exist yet. Leaving it only in
    the final build-review section means an early voice turn sounds like Locah
    silently accepted the request. Keep the next question, but lead with the
    deterministic platform answer the owner needs to hear now.
    """
    new_gaps = [
        gap for gap in bp.unsupported_requests if gap.normalized_intent not in previous_intents
    ]
    if not new_gaps:
        return
    for index in range(len(bp.messages) - 1, -1, -1):
        message = bp.messages[index]
        if message.role != "assistant":
            continue
        notice = (
            "That request is not supported today and will not be added to your website. "
        )
        if not message.text.startswith(notice):
            bp.messages[index] = Message(
                role="assistant", text=notice + message.text, at=message.at
            )
        return


def operational_modules(entitlement: ResolvedEntitlement) -> set[str]:
    """A more restrictive input to composition than activation alone."""
    active = {
        mid
        for mid, state in entitlement.module_states.items()
        if state.entitled
        and state.activation_state == "active"
        and state.configuration_ready
        and state.dependency_satisfied
    }
    snapshot = PlatformCapabilityResolver.resolve_from_entitlement(entitlement)
    for cap, definition in CAPABILITIES.items():
        if not snapshot.capabilities.get(cap) and definition.required_module_id:
            active.discard(definition.required_module_id)
    for module in list(active):
        definition = ModuleRegistry.get_or_raise(module)
        if definition.features and not all(
            entitlement.feature_states.get(fid) and entitlement.feature_states[fid].enabled
            for fid in definition.features[:1]
        ):
            active.discard(module)
    changed = True
    while changed:
        removed = {
            mid
            for mid in active
            if not set(ModuleRegistry.get_or_raise(mid).dependencies) <= active
        }
        active -= removed
        changed = bool(removed)
    return active
