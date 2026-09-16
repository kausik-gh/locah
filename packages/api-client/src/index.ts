// Typed API Client placeholder
export class ApiClient {
  private baseUrl: string

  constructor(config: { baseUrl: string }) {
    this.baseUrl = config.baseUrl
  }

  async getHealth(): Promise<{ status: string }> {
    const res = await fetch(`${this.baseUrl}/health/live`)
    if (!res.ok) {
      throw new Error('API liveness check failed')
    }
    return res.json()
  }
}
