/** Business Interview v1. Server authority: platform_core.interview.models. */
export type InterviewFactKey = 'description' | 'classification' | 'operating_model' | 'locations'
  | 'offerings' | 'customer_actions' | 'operational_characteristics' | 'brand' | 'tone'
  | 'colours' | 'opening_hours' | 'phone' | 'email' | 'website_priorities'
export type InterviewFact = {
  value: string; source: 'USER_STATEMENT' | 'PLATFORM' | 'AI_EXTRACTION'
  confirmation: 'confirmed' | 'unconfirmed'; evidence: string; updated_at: string
}
export type InterviewMedia = {
  asset_id: string; role: 'logo' | 'hero' | 'business' | 'offering' | 'gallery'
  label: string; source: 'USER_UPLOAD' | 'AI_GENERATED'
}
export type InterviewModule = {
  module_id: string; label: string; reason: string; capability_ids: string[]; dependencies: string[]
  status: 'SUPPORTED' | 'SUPPORTED_REQUIRES_CONFIGURATION' | 'SUPPORTED_NOT_ENABLED' | 'NOT_CURRENTLY_AVAILABLE'
  availability_reason: string; choice: 'pending' | 'approved' | 'declined'
  /** Who the tool is for: the owner's customers, or running the business. */
  group?: 'customer' | 'operations'
  /** How strongly the conversation points at it; `dependency` = another tool needs it. */
  strength?: 'strong' | 'useful' | 'dependency'
  evidence?: { kind: 'owner_said' | 'operating_model' | 'answer' | 'dependency' | 'profile'; text: string }[]
  /** What still has to be set up before customers can use it. */
  configuration_needed?: string
  /** Owner-facing names of the tools that need this one. */
  needed_by?: string[]
}
export type DiscoveryTargetStatus = 'open' | 'asked' | 'partial' | 'answered' | 'declined' | 'deferred'
/** What Locah knows about one concept (not one question), and how often it asked. */
export type DiscoveryTarget = {
  status: DiscoveryTargetStatus; asked: number; last_asked_turn: number | null
  summary: string; quote: string
}
export type DraftProvenance = 'ai_suggestion' | 'owner_claim' | 'owner_edited' | 'owner_approved'
export type DraftText = { text: string; provenance: DraftProvenance; updated_at: string }
/** Website wording beside the conversation. Presentation, never business truth. */
export type WebsiteDraft = {
  hero_headline: DraftText | null; hero_subheadline: DraftText | null
  about: DraftText | null; cta_label: DraftText | null
  offerings: { name: string; description: DraftText | null }[]
  owner_claims: { claim: string; quote: string }[]
  dismissed: string[]
}
export type DraftField = 'hero_headline' | 'hero_subheadline' | 'about' | 'cta_label' | 'offering'
export type DraftCommand = {
  field: DraftField; op: 'edit' | 'approve' | 'dismiss' | 'regenerate'
  text?: string; offering_name?: string
}
export type InterviewReadiness = { ready: boolean; missing: string[]; reason: string }
/** The side panel: built from state by the server, never a fact dump. */
export type InterviewUnderstanding = {
  kind: string
  traits: string[]
  customer_steps: string[]
  items: { label: string; value: string; status: 'confirmed' | 'from_you'; target: string }[]
  still_worth_knowing: { id: string; label: string; essential: boolean }[]
  readiness: InterviewReadiness
  logo:
    | { state: 'none' }
    | { state: 'ready'; source: 'USER_UPLOAD' | 'AI_GENERATED'; url: string | null }
    | { state: 'requested' | 'unavailable' | 'queued' | 'failed'; reason: string | null }
}
export type BusinessBlueprint = {
  schema_version: 1; business_id: string; session_id: string; revision: number
  created_at: string; updated_at: string; transport: 'chat' | 'voice'; turn_count: number
  identity: Record<string, InterviewFact>; business_classification: InterviewFact | null
  operating_model: InterviewFact | null; locations: InterviewFact | null; offerings: InterviewFact | null
  customer_actions: InterviewFact | null; operational_characteristics: InterviewFact | null
  brand: InterviewFact | null; tone: InterviewFact | null; colours: InterviewFact | null
  logo_state: 'not_supplied' | 'uploaded' | 'generation_requested' | 'generated'
  media_assets: InterviewMedia[]
  media_generation_requests: { role: 'hero' | 'logo'
    status: 'requested' | 'unavailable' | 'queued' | 'ready' | 'failed'
    reason: string | null; asset_id: string | null }[]
  requested_capabilities: { intent: string; original_request: string }[]
  recommended_modules: InterviewModule[]; declined_modules: string[]; approved_modules: string[]
  website_content: Record<string, InterviewFact>; website_priorities: InterviewFact | null
  template_preferences: { template_id: string | null; source: 'PLATFORM' | 'USER_STATEMENT' }
  known_facts: Partial<Record<InterviewFactKey, InterviewFact>>
  suggested_content: Record<string, { text: string; source: 'AI_SUGGESTION'; confirmation: 'confirmed' | 'unconfirmed' }>
  unconfirmed_facts: Partial<Record<InterviewFactKey, InterviewFact>>
  unsupported_requests: { original_request: string; normalized_intent: string; business_classification: string
    closest_supported_capabilities: string[]; why_unsupported: string; required_mechanics: string[]; session_reference: string }[]
  remaining_questions: { field: InterviewFactKey; text: string; reason: string }[]
  completion_state: { status: 'collecting' | 'review' | 'ready' | 'built'; sufficient: boolean; confirmed: boolean
    completed_at: string | null; first_preview_at: string | null; generation_job_id: string | null }
  messages: { role: 'user' | 'assistant'; text: string; at: string }[]
  last_turn: { provider: string; model: string; latency_ms: number; input_tokens: number | null
    output_tokens: number | null; cost: number | null; retries: number; fallback_reason: string | null } | null
  applied_requests: string[]
  /** How the owner talks: Locah answers in the same mix. */
  language_style: 'en' | 'ta' | 'ta_en' | 'hi' | 'hi_en' | 'other'
  operating_patterns: { pattern: string; quote: string }[]
  /** Numbers the owner said, verified against their own words. */
  highlights: { value: string; label: string; quote: string }[]
  asked_optional: ('locations' | 'phone' | 'logo')[]
  /** Discovery state per concept ("offerings.units", "fulfilment.mode", ...). */
  discovery: Record<string, DiscoveryTarget>
  last_asked_target: string | null
  website_draft: WebsiteDraft
  readiness: InterviewReadiness
}
export type BusinessInterviewData = {
  blueprint: BusinessBlueprint; classification_seed: string
  understanding: InterviewUnderstanding
  available_modules: InterviewModule[]
  templates: { id: string; name: string; description: string; primary_color: string; accent_color: string
    available: boolean; look: string[]; page_count: number }[]
  voice: { available: boolean; reason: string }
  image_generation: { available: boolean; reason: string }
}
export type InterviewCommand = {
  revision: number; request_id: string
  action: 'turn' | 'confirm' | 'choices' | 'template' | 'media' | 'image' | 'build' | 'draft'
  text?: string; field?: InterviewFactKey; choices?: Record<string, 'approved' | 'declined'>
  template_id?: string; media?: InterviewMedia
  /** For action 'image': what to draw. */
  image_role?: 'hero' | 'logo'
  /** For action 'draft': edit, keep, remove or rewrite one piece of website wording. */
  draft?: DraftCommand
}
