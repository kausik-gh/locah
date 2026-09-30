/**
 * Recorded voice for tests — no microphone, no socket, no provider.
 *
 * The server hands this out only when VOICE_PROVIDER=replay AND every paid
 * AI call is switched off (LOCAH_TEST_NO_EXTERNAL_AI=1); it can never stand
 * in for real voice on a deployed server. It "hears" the fixture's
 * utterances one by one and moves through exactly the states a real session
 * does, so the Talk-to-LOCAH UI and the shared conversation can be tested
 * end to end without spending anything.
 */

import type { VoiceCallbacks } from './types'

export type ReplaySession = { provider: 'replay'; utterances: string[] }

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

export class ReplayVoiceConnection {
  private stopped = false

  constructor(private readonly cb: VoiceCallbacks) {}

  async start(session: ReplaySession): Promise<void> {
    this.cb.onState('requesting-mic')
    await wait(250)
    if (this.stopped) return
    this.cb.onState('listening')
    for (const [i, line] of session.utterances.entries()) {
      await wait(900)
      if (this.stopped) return
      this.cb.onState('user-speaking')
      const words = line.split(/\s+/)
      for (let n = 1; n <= words.length; n += 1) {
        if (this.stopped) return
        this.cb.onTranscript({
          role: 'user',
          text: words.slice(0, n).join(' '),
          at: Date.now(),
          id: `replay-user-${i}`,
          final: n === words.length,
        })
        await wait(35)
      }
      this.cb.onState('thinking')
      const { say } = await this.cb.onTurn(line)
      if (this.stopped) return
      this.cb.onState('speaking')
      this.cb.onTranscript({ role: 'assistant', text: say, at: Date.now(), id: `replay-locah-${i}`, final: true })
      await wait(Math.min(2400, 500 + say.length * 10))
      if (this.stopped) return
      this.cb.onState('listening')
    }
    await wait(500)
    if (!this.stopped) this.cb.onState('ended')
  }

  setMuted(): void {}

  stop(): void {
    this.stopped = true
    this.cb.onState('ended')
  }
}
