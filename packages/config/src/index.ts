import { z } from 'zod'

export const envSchema = z.object({
  NEXT_PUBLIC_API_URL: z.string().url(),
  NEXT_PUBLIC_SUPABASE_URL: z.string().url(),
  NEXT_PUBLIC_SUPABASE_ANON_KEY: z.string().min(1),
  PLATFORM_DOMAIN: z.string().default('localhost'),
  NEXT_PUBLIC_PLATFORM_DOMAIN: z.string().default('localhost'),
  ENVIRONMENT: z.enum(['local', 'test', 'staging', 'production']).default('local'),
})

export type Env = z.infer<typeof envSchema>

export function validateEnv(config: Record<string, unknown>): Env {
  const result = envSchema.safeParse(config)
  if (!result.success) {
    console.error('❌ Invalid environment variables:', result.error.format())
    throw new Error('Invalid environment configuration')
  }
  return result.data
}
