// Phase A browser acceptance: Create Business → Talk to LOCAH → confirm →
// build → website, driven in a real (headless) Chrome against the LOCAL stack.
//
//   node tools/acceptance/flows.mjs [A B C …]
//
// Needs the local stack from tools/acceptance/README.md: local Postgres, the
// mock auth, the API with LOCAH_TEST_NO_EXTERNAL_AI=1 + recorded model and
// voice, the web app. Nothing here reaches a paid provider: the API refuses
// every AI call, and messages without a recording take the model-down path.
//
// Each flow answers LOCAH the way its persona would (whatever LOCAH asks,
// read from the interview state), asserts what must be true, and saves
// screenshots + a transcript to $LOCAH_ACCEPT_OUT/<flow>/.

import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { launch } from './cdp.mjs'

const WEB = process.env.LOCAH_WEB || 'http://localhost:3100'
const API = process.env.LOCAH_API || 'http://localhost:8010'
const OUT = process.env.LOCAH_ACCEPT_OUT || path.resolve('acceptance-out')
const session = JSON.parse(readFileSync(process.env.LOCAH_ACCEPT_SESSION, 'utf8'))
const personas = JSON.parse(readFileSync(process.env.LOCAH_ACCEPT_PERSONAS, 'utf8'))
const VOICE_FILE = process.env.LOCAH_VOICE_REPLAY_FILE
const NOT_SURE = 'Not sure about that — you decide.'
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function api(p, init = {}) {
  const res = await fetch(`${API}${p}`, {
    ...init,
    headers: { Authorization: `Bearer ${session.token}`, 'Content-Type': 'application/json', ...(init.headers || {}) },
  })
  if (!res.ok) throw new Error(`${p}: ${res.status} ${await res.text()}`)
  return (await res.json()).data
}

class Flow {
  constructor(id, title) {
    this.id = id
    this.title = title
    this.dir = path.join(OUT, id)
    mkdirSync(this.dir, { recursive: true })
    this.checks = []
    this.shots = []
    this.notes = []
  }
  check(label, ok, detail = '') {
    this.checks.push({ label, ok: Boolean(ok), detail: String(detail).slice(0, 400) })
    if (!ok) console.log(`   ✗ ${label} ${detail}`)
  }
  async shot(page, name, opts) {
    const file = path.join(this.dir, `${name}.png`)
    await page.shot(file, opts)
    this.shots.push(path.relative(OUT, file))
  }
}

async function businessId(page) {
  const url = await page.url()
  const m = /\/start\/([0-9a-f-]{36})/.exec(url)
  return m ? m[1] : ''
}

async function interview(id) {
  return api(`/v1/b/${id}/interview`)
}

/** Type a reply in the composer and wait for LOCAH's answer to land. */
async function reply(page, id, text) {
  const before = (await interview(id)).blueprint.revision
  await page.type('#ti-input', text)
  await page.click('button.ti-send')
  for (let i = 0; i < 150; i++) {
    await sleep(200)
    const now = await interview(id)
    if (now.blueprint.revision > before) {
      await page.waitGone('.ti-thinking', 20000).catch(() => {})
      await sleep(300)
      return now
    }
  }
  throw new Error(`no answer to: ${text}`)
}

/** Answer whatever LOCAH asks, as the persona would, until the checkpoint. */
async function converse(page, id, persona, flow, { maxTurns = 9 } = {}) {
  let data = await interview(id)
  for (let turn = 0; turn < maxTurns; turn++) {
    const bp = data.blueprint
    if (bp.checkpoint_turn != null && bp.completion_state.ready_at) break
    const ask = bp.asks.at(-1)?.ask || ''
    const text = ask === 'name' ? persona.name : persona.answers[ask] || NOT_SURE
    data = await reply(page, id, text)
    flow.notes.push(`asked ${ask} → answered`)
  }
  return data
}

function followUps(bp) {
  return bp.asks.filter((a) => !['opening', 'free'].includes(a.ask)).length
}

function transcript(bp) {
  return bp.messages
    .map((m) => `**${m.role === 'assistant' ? 'LOCAH' : m.via === 'voice' ? 'OWNER (spoken)' : 'OWNER'}:** ${m.text}`)
    .join('\n\n')
}

async function startTyped(page, text, kindQuery = '') {
  await page.goto(`${WEB}/start`)
  await page.waitFor('#st-about')
  if (kindQuery) {
    await page.type('.ks-field input', kindQuery)
    await page.waitFor('.ks-results li', { timeout: 10000 })
    await page.click('.ks-results li')
  }
  if (text) await page.type('#st-about', text)
  await page.click('button.st-send')
  await page.waitFor('.ti-log', { timeout: 60000 })
  await page.waitGone('.ti-thinking', 30000).catch(() => {})
  return businessId(page)
}

/** Build from the confirmation sheet, through the transition, to the website. */
async function build(page, flow, id) {
  await page.click('button.ti-bar__build')
  await page.waitFor('.cs', { timeout: 10000 })
  await flow.shot(page, 'confirm')
  const sheet = await page.text('.cs')
  flow.check('confirmation shows the business name', sheet.length > 40, sheet.slice(0, 120))
  await page.click('button.cs-build')
  await page.waitFor('.bo', { timeout: 5000 }).catch(() => {})
  await flow.shot(page, 'building').catch(() => {})
  for (let i = 0; i < 150 && !(await page.url()).includes('/website'); i++) await sleep(200)
  await page.waitFor('iframe', { timeout: 60000 })
  await sleep(2500)
  await flow.shot(page, 'website')
  const bp = (await interview(id)).blueprint
  flow.check('built', bp.completion_state.status === 'built', bp.completion_state.status)
}

async function standardConversation(page, flow, persona, { typedOpening = true, kindQuery = '' } = {}) {
  const id = await startTyped(page, typedOpening ? persona.opening : '', kindQuery)
  flow.check('conversation opened', Boolean(id))
  await flow.shot(page, 'first-reply')
  let data = await interview(id)
  if (!typedOpening) data = await reply(page, id, persona.opening)
  data = await converse(page, id, persona, flow)
  const bp = data.blueprint
  flow.result = {
    followUps: followUps(bp),
    checkpointAfter: bp.checkpoint_turn != null ? followUps(bp) : null,
    asks: bp.asks.map((a) => a.ask),
    category: data.understanding.business.category,
    name: data.understanding.business.name,
  }
  flow.check('reached "enough for a strong first version"', bp.completion_state.ready_at != null)
  flow.check('Build is offered', data.build_available === true)
  flow.check(
    'question budget (≤ 8 follow-ups)',
    followUps(bp) <= 8,
    `${followUps(bp)} follow-ups: ${flow.result.asks.join(', ')}`
  )
  flow.check(
    'no question asked twice in a row',
    bp.asks.every((a, i) => i === 0 || a.ask === 'free' || a.ask !== bp.asks[i - 1].ask)
  )
  await flow.shot(page, 'checkpoint')
  return { id, data }
}

// ------------------------------------------------------------------ flows

const FLOWS = {
  async A(page) {
    const flow = new Flow('A-talk-first-meat-shop', 'Talk-first meat shop (typed first message, no category, no name)')
    const persona = personas['meat-shop-talk']
    const { id, data } = await standardConversation(page, flow, persona)
    const first = data.blueprint.messages[2]?.text || ''
    flow.check('understands first: reads the business back', /^Got it — a meat shop/.test(first), first)
    flow.check('asks the name once', data.blueprint.asks.filter((a) => a.ask === 'name').length === 1)
    flow.check('kind read from what was said', data.understanding.business.category === 'Meat shop')
    const actions = data.understanding.actions.map((a) => a.label)
    flow.check('customer actions are actions', actions.includes('Order on WhatsApp'), actions.join(', '))
    await build(page, flow, id)
    flow.transcript = transcript((await interview(id)).blueprint)
    return flow
  },

  async B(page) {
    const flow = new Flow('B-category-first-restaurant', 'Category-first restaurant')
    const persona = personas.restaurant
    const id = await startTyped(page, '', 'restaurant')
    const opening = (await interview(id)).blueprint.messages[0].text
    flow.check('opening acknowledges the picked kind', /^Got it — a restaurant\./.test(opening), opening)
    await flow.shot(page, 'opening')
    await reply(page, id, persona.opening)
    const data = await converse(page, id, persona, flow)
    flow.result = { followUps: followUps(data.blueprint), asks: data.blueprint.asks.map((a) => a.ask) }
    flow.check('reached checkpoint', data.blueprint.completion_state.ready_at != null)
    flow.check('category kept as picked', data.understanding.business.category_source === 'owner_picked')
    await flow.shot(page, 'checkpoint')
    flow.transcript = transcript(data.blueprint)
    return flow
  },

  async C(page) {
    const flow = new Flow('C-talk-first-gym-voice', 'Talk-first gym, by voice')
    const persona = personas['gym-talk']
    writeFileSync(VOICE_FILE, JSON.stringify({ utterances: [persona.opening] }))
    await page.goto(`${WEB}/start`)
    await page.waitFor('#st-about')
    await page.click('button.st-talk')
    await page.waitFor('.ti-voice', { timeout: 60000 })
    const id = await businessId(page)
    await sleep(1500)
    await flow.shot(page, 'listening')
    await page.waitFor('.ti-voice[data-phase="speaking"]', { timeout: 30000 }).catch(() => {})
    await flow.shot(page, 'speaking')
    await page.waitFor('.ti-compose', { timeout: 30000 })
    let data = await interview(id)
    const spoken = data.blueprint.messages.filter((m) => m.role === 'user')
    flow.check('the spoken answer is in the conversation', spoken[0]?.via === 'voice', JSON.stringify(spoken[0]))
    flow.check('name read from speech', data.understanding.business.name === 'Grit Barbell Club', data.understanding.business.name)
    data = await converse(page, id, persona, flow)
    flow.check('typed answers continue the spoken conversation', data.blueprint.messages.some((m) => m.role === 'user' && m.via === 'text'))
    flow.check('reached checkpoint', data.blueprint.completion_state.ready_at != null)
    flow.result = { followUps: followUps(data.blueprint), asks: data.blueprint.asks.map((a) => a.ask) }
    await flow.shot(page, 'checkpoint')
    flow.transcript = transcript(data.blueprint)
    return flow
  },

  async D(page) {
    const flow = new Flow('D-salon', 'Salon (owner writes Tamil)')
    const persona = personas.salon
    const { data } = await standardConversation(page, flow, persona)
    flow.check('kind read from Tamil', data.understanding.business.category === 'Salon', data.understanding.business.category)
    flow.transcript = transcript(data.blueprint)
    return flow
  },

  async E(page) {
    const flow = new Flow('E-real-estate', 'Real-estate developer')
    const persona = personas['real-estate-talk']
    const { id, data } = await standardConversation(page, flow, persona)
    flow.check('a developer, not a villa rental', data.understanding.business.category === 'Property developer', data.understanding.business.category)
    await build(page, flow, id)
    flow.transcript = transcript((await interview(id)).blueprint)
    return flow
  },

  async F(page) {
    const flow = new Flow('F-photographer', 'Wedding photographer')
    const persona = personas['photographer-talk']
    const { id, data } = await standardConversation(page, flow, persona)
    flow.check('photographer', /photographer/i.test(data.understanding.business.category), data.understanding.business.category)
    await build(page, flow, id)
    flow.transcript = transcript((await interview(id)).blueprint)
    return flow
  },

  async G(page) {
    const flow = new Flow('G-industrial-supplier', 'Industrial supplier (B2B, quotes)')
    const persona = personas['industrial-talk']
    const { id, data } = await standardConversation(page, flow, persona)
    const actions = data.understanding.actions.map((a) => a.id)
    flow.check('asks for a quote, not a booking', actions.includes('request_quote') && !actions.some((a) => a.startsWith('book')), actions.join(','))
    await build(page, flow, id)
    flow.transcript = transcript((await interview(id)).blueprint)
    return flow
  },

  async H(page) {
    const flow = new Flow('H-model-unavailable', 'Model/provider unavailable (no recording for any message)')
    const persona = {
      name: 'Kavya Bakes',
      opening: 'Kavya Bakes is a home bakery in Saibaba Colony. We make custom cakes and brownies, people order on WhatsApp.',
      answers: {
        structure: 'Cakes - chocolate truffle, red velvet. Brownies - walnut and fudge.',
        fulfilment: 'Pickup from our home in Saibaba Colony, and we deliver nearby.',
        contact: 'Saibaba Colony, Coimbatore. 9876512345.',
        phone: '9876512345',
        conversion: 'They order on WhatsApp.',
        offer: 'Custom cakes and brownies.',
      },
    }
    const { data } = await standardConversation(page, flow, persona)
    flow.check('no model: the turn records its fallback', Boolean(data.blueprint.last_turn?.fallback_reason), data.blueprint.last_turn?.fallback_reason)
    flow.check('nothing misfiled into hours', data.understanding.contact.hours === '', data.understanding.contact.hours)
    flow.transcript = transcript(data.blueprint)
    return flow
  },

  async I(page) {
    const flow = new Flow('I-owner-says-build-it', 'Owner says "Build it" mid-way')
    const persona = personas['meat-shop']
    const id = await startTyped(page, persona.opening + ' The shop is called Ishant Proteins.')
    let data = await interview(id)
    const ask = data.blueprint.asks.at(-1).ask
    data = await reply(page, id, persona.answers[ask] || NOT_SURE)
    data = await reply(page, id, 'That’s all, build it.')
    await page.waitFor('.cs', { timeout: 10000 })
    flow.check('asking to build opens the confirmation', true)
    flow.check('Build stays available', data.build_available === true)
    await flow.shot(page, 'confirm-after-build-it')
    flow.transcript = transcript(data.blueprint)
    return flow
  },

  async J(page) {
    const flow = new Flow('J-keep-refining', 'Owner chooses "Keep refining" at the checkpoint')
    const persona = personas.gym
    const { id, data } = await standardConversation(page, flow, persona)
    const before = data.blueprint.asks.length
    await page.click('Keep refining', { byText: true })
    for (let i = 0; i < 50; i++) {
      await sleep(200)
      if ((await interview(id)).blueprint.refining) break
    }
    const after = await interview(id)
    flow.check('a next question is asked', after.blueprint.asks.length === before + 1, after.blueprint.asks.at(-1)?.ask)
    flow.check('Build never disappears', after.build_available === true)
    await sleep(500)
    await flow.shot(page, 'refining')
    const again = await reply(page, id, persona.answers[after.blueprint.asks.at(-1).ask] || NOT_SURE)
    flow.check('Build still there after another answer', again.build_available === true)
    flow.transcript = transcript(again.blueprint)
    return flow
  },

  async K(page) {
    const flow = new Flow('K-correct-a-fact', 'Owner corrects a side-panel fact (structured Change)')
    const persona = personas['meat-shop']
    const { id } = await standardConversation(page, flow, persona)
    await page.click('button[aria-label="Change how customers reach you"]')
    await page.waitFor('.up-toggles', { timeout: 5000 })
    await flow.shot(page, 'editing')
    await page.click('Order online', { byText: true })
    await page.click('.up-edit__actions button[type=submit]')
    for (let i = 0; i < 50; i++) {
      await sleep(200)
      const now = await interview(id)
      if (now.understanding.actions.some((a) => a.id === 'order_online')) break
    }
    const now = await interview(id)
    flow.check('the owner’s choice wins', now.understanding.actions.map((a) => a.id).includes('order_online'))
    flow.check('readiness kept after the change', now.build_available === true && now.blueprint.completion_state.ready_at != null)
    await flow.shot(page, 'corrected')
    // Change the kind of business in words, mid-conversation.
    const kind = await reply(page, id, 'No, actually we are mainly a butcher shop.')
    flow.check('kind corrected by saying so', kind.understanding.business.category === 'Butcher', kind.understanding.business.category)
    flow.check('Build still available', kind.build_available === true)
    flow.transcript = transcript(kind.blueprint)
    return flow
  },

  async L(page) {
    const flow = new Flow('L-voice-then-text', 'Voice transcript → text continuation')
    const persona = personas['meat-shop-talk']
    writeFileSync(VOICE_FILE, JSON.stringify({ utterances: [persona.opening] }))
    await page.goto(`${WEB}/start`)
    await page.waitFor('#st-about')
    await page.click('button.st-talk')
    await page.waitFor('.ti-voice', { timeout: 60000 })
    const id = await businessId(page)
    await page.waitFor('.ti-compose', { timeout: 40000 })
    let data = await interview(id)
    flow.check('spoken first answer understood', data.understanding.business.category === 'Meat shop')
    flow.check('LOCAH asked for the name', data.blueprint.asks.at(-1).ask === 'name')
    await flow.shot(page, 'after-voice')
    data = await reply(page, id, 'Ishant Proteins')
    flow.check('typed name continues the same conversation', data.understanding.business.name === 'Ishant Proteins')
    const vias = data.blueprint.messages.filter((m) => m.role === 'user').map((m) => m.via)
    flow.check('one conversation: spoken then typed', vias.join(',') === 'voice,text', vias.join(','))
    await flow.shot(page, 'typed-after-voice')
    flow.transcript = transcript(data.blueprint)
    return flow
  },
}

// ------------------------------------------------------------------- run

const wanted = process.argv.slice(2).length ? process.argv.slice(2) : Object.keys(FLOWS)
const mobile = process.env.LOCAH_ACCEPT_MOBILE === '1'
const results = []
for (const key of wanted) {
  const page = await launch(mobile ? { width: 390, height: 844, mobile: true } : { width: 1440, height: 900 })
  await page.cookie(session.cookie_name, session.cookie, WEB)
  const started = Date.now()
  let flow
  try {
    console.log(`▶ ${key}`)
    flow = await FLOWS[key](page)
  } catch (e) {
    flow = new Flow(`${key}-error`, key)
    flow.check('ran to the end', false, e.stack || e.message)
    await flow.shot(page, 'error').catch(() => {})
  }
  flow.seconds = Math.round((Date.now() - started) / 1000)
  flow.consoleErrors = page.consoleErrors.filter((e) => e && !/Download the React DevTools/.test(e))
  await page.close()
  writeFileSync(path.join(flow.dir, 'transcript.md'), `# ${flow.title}\n\n${flow.transcript || ''}\n`)
  results.push({
    id: flow.id,
    title: flow.title,
    passed: flow.checks.every((c) => c.ok),
    checks: flow.checks,
    result: flow.result || null,
    shots: flow.shots,
    seconds: flow.seconds,
    consoleErrors: flow.consoleErrors,
  })
  console.log(`  ${flow.checks.every((c) => c.ok) ? 'PASS' : 'FAIL'} ${flow.id} (${flow.seconds}s)`)
}
writeFileSync(path.join(OUT, mobile ? 'results-mobile.json' : 'results.json'), JSON.stringify(results, null, 1))
const failed = results.filter((r) => !r.passed)
console.log(`${results.length - failed.length}/${results.length} flows passed`)
process.exit(failed.length ? 1 : 0)
