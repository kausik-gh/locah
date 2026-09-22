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
}
export type BusinessBlueprint = {
  schema_version: 1; business_id: string; session_id: string; revision: number
  created_at: string; updated_at: string; transport: 'chat' | 'voice'; turn_count: number
  identity: Record<string, InterviewFact>; business_classification: InterviewFact | null
  operating_model: InterviewFact | null; locations: InterviewFact | null; offerings: InterviewFact | null
  customer_actions: InterviewFact | null; operational_characteristics: InterviewFact | null
  brand: InterviewFact | null; tone: InterviewFact | null; colours: InterviewFact | null
  logo_state: 'not_supplied' | 'uploaded' | 'generation_requested'; media_assets: InterviewMedia[]
  media_generation_requests: { role: 'hero' | 'logo'; status: string; reason: string | null; asset_id: string | null }[]
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
}
export type BusinessInterviewData = {
  blueprint: BusinessBlueprint; classification_seed: string
  templates: { id: string; name: string; description: string; primary_color: string; accent_color: string
    available: boolean; look: string[]; page_count: number }[]
  voice: { available: boolean; reason: string }
  image_generation: { available: boolean; reason: string }
}
export type InterviewCommand = {
  revision: number; request_id: string
  action: 'turn' | 'confirm' | 'choices' | 'template' | 'media' | 'image' | 'build'
  text?: string; field?: InterviewFactKey; choices?: Record<string, 'approved' | 'declined'>
  template_id?: string; media?: InterviewMedia
}
