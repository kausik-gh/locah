// A tiny Chrome DevTools Protocol driver for LOCAH's local acceptance runs.
//
// No Playwright, no downloads: it drives the Chrome already installed, over
// the DevTools socket, headless. Enough to sign in with a local test session,
// type, click, wait for text and take exact-viewport screenshots at desktop
// and phone sizes. Used by flows.mjs against the LOCAL stack only.

import { spawn } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'
import os from 'node:os'
import path from 'node:path'

const CHROME =
  process.env.CHROME_PATH ||
  ({
    win32: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    darwin: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  }[process.platform] ?? 'google-chrome')
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

export async function launch({ width = 1440, height = 900, mobile = false } = {}) {
  const port = 9300 + Math.floor(Math.random() * 500)
  const userDir = path.join(process.env.TEMP || os.tmpdir(), `locah-accept-${port}`)
  mkdirSync(userDir, { recursive: true })
  const proc = spawn(
    CHROME,
    [
      '--headless=new',
      '--disable-gpu',
      '--hide-scrollbars',
      `--remote-debugging-port=${port}`,
      `--user-data-dir=${userDir}`,
      '--no-first-run',
      '--no-default-browser-check',
      '--use-fake-ui-for-media-stream',
      '--use-fake-device-for-media-stream',
      // Containers run as root, where Chrome refuses to start sandboxed.
      ...(process.env.CHROME_NO_SANDBOX ? ['--no-sandbox'] : []),
      'about:blank',
    ],
    { stdio: 'ignore' }
  )
  let targets = []
  for (let i = 0; i < 160; i++) {  // up to 40 s: a cold Chrome on a busy machine
    try {
      targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json()
      if (targets.find((t) => t.type === 'page')) break
    } catch {}
    await sleep(250)
  }
  const target = targets.find((t) => t.type === 'page')
  if (!target) {
    proc.kill()
    throw new Error(`Chrome did not offer a page on port ${port}`)
  }
  const ws = new WebSocket(target.webSocketDebuggerUrl)
  // Never wait forever on the DevTools socket; a stuck launch should fail loudly.
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('DevTools socket did not open within 15 s')), 15000)
    ws.addEventListener('open', () => { clearTimeout(timer); resolve() })
    ws.addEventListener('error', () => { clearTimeout(timer); reject(new Error('DevTools socket error')) })
  })
  let id = 0
  const pending = new Map()
  const events = []
  const consoleErrors = []
  ws.addEventListener('message', (m) => {
    const msg = JSON.parse(m.data)
    if (msg.id && pending.has(msg.id)) {
      pending.get(msg.id)(msg)
      pending.delete(msg.id)
    } else if (msg.method) {
      events.push(msg.method)
      if (msg.method === 'Runtime.exceptionThrown') consoleErrors.push(msg.params.exceptionDetails?.text || 'exception')
      if (msg.method === 'Runtime.consoleAPICalled' && msg.params.type === 'error')
        consoleErrors.push(msg.params.args?.map((a) => a.value ?? a.description).join(' '))
    }
  })
  const send = (method, params = {}) =>
    new Promise((resolve) => {
      const n = ++id
      pending.set(n, resolve)
      ws.send(JSON.stringify({ id: n, method, params }))
    })

  await send('Page.enable')
  await send('Runtime.enable')
  await send('Network.enable')
  const page = {
    width,
    height,
    mobile,
    consoleErrors,
    async viewport(w, h, isMobile = false) {
      page.width = w
      page.height = h
      page.mobile = isMobile
      await send('Emulation.setDeviceMetricsOverride', {
        width: w,
        height: h,
        deviceScaleFactor: isMobile ? 2 : 1,
        mobile: isMobile,
      })
      await send('Emulation.setTouchEmulationEnabled', { enabled: isMobile })
    },
    /** Cut or restore the page's network, as a lost connection would (§14.2 offline tests). */
    async offline(on) {
      await send('Network.emulateNetworkConditions', { offline: !!on, latency: 0, downloadThroughput: -1, uploadThroughput: -1 })
    },
    /** Render as print (e.g. to check a receipt's print layout) or back to screen. */
    async media(type) {
      await send('Emulation.setEmulatedMedia', { media: type || '' })
    },
    async cookie(name, value, url) {
      await send('Network.setCookie', { name, value, url, path: '/' })
    },
    async goto(url) {
      events.length = 0
      await send('Page.navigate', { url })
      for (let i = 0; i < 160 && !events.includes('Page.loadEventFired'); i++) await sleep(250)
      await sleep(600)
    },
    async eval(expression) {
      const res = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
      if (res.result?.exceptionDetails) throw new Error(res.result.exceptionDetails.text + ' in ' + expression.slice(0, 120))
      return res.result?.result?.value
    },
    url() {
      return page.eval('location.href')
    },
    /** Wait until a selector exists, or text appears in the page. */
    async waitFor(what, { timeout = 30000, text = false } = {}) {
      const started = Date.now()
      const probe = text
        ? `document.body && document.body.innerText.includes(${JSON.stringify(what)})`
        : `!!document.querySelector(${JSON.stringify(what)})`
      while (Date.now() - started < timeout) {
        if (await page.eval(probe)) return true
        await sleep(200)
      }
      throw new Error(`timed out waiting for ${text ? 'text' : 'selector'}: ${what}`)
    },
    async waitGone(selector, timeout = 30000) {
      const started = Date.now()
      while (Date.now() - started < timeout) {
        if (!(await page.eval(`!!document.querySelector(${JSON.stringify(selector)})`))) return true
        await sleep(200)
      }
      throw new Error(`still present: ${selector}`)
    },
    /** Set a React-controlled input/textarea value the way a user would. */
    async type(selector, value) {
      await page.eval(`(() => {
        const el = document.querySelector(${JSON.stringify(selector)});
        if (!el) throw new Error('no element ${selector.replace(/'/g, '')}');
        el.focus();
        const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
        Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, ${JSON.stringify(value)});
        el.dispatchEvent(new Event('input', { bubbles: true }));
        return true;
      })()`)
      await sleep(150)
    },
    /** Click an element by selector, or the first button/link whose text matches. */
    async click(what, { byText = false } = {}) {
      const ok = await page.eval(`(() => {
        let el;
        if (${byText}) {
          const want = ${JSON.stringify(what)}.toLowerCase();
          el = [...document.querySelectorAll('button, a, [role=option], li[role=option]')]
            .find((e) => e.offsetParent !== null && e.innerText.trim().toLowerCase() === want)
            || [...document.querySelectorAll('button, a')].find((e) => e.offsetParent !== null && e.innerText.trim().toLowerCase().startsWith(want));
        } else {
          el = document.querySelector(${JSON.stringify(what)});
        }
        if (!el) return false;
        el.scrollIntoView({ block: 'center' });
        el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
        el.click();
        return true;
      })()`)
      if (!ok) throw new Error(`nothing to click: ${what}`)
      await sleep(250)
    },
    async text(selector) {
      return page.eval(`(document.querySelector(${JSON.stringify(selector)}) || {}).innerText || ''`)
    },
    async shot(out, { full = false } = {}) {
      mkdirSync(path.dirname(out), { recursive: true })
      await sleep(500)
      let clip
      if (full) {
        const h = await page.eval('document.documentElement.scrollHeight')
        await send('Emulation.setDeviceMetricsOverride', {
          width: page.width,
          height: Math.min(h, 12000),
          deviceScaleFactor: page.mobile ? 2 : 1,
          mobile: page.mobile,
        })
        await sleep(700)
        clip = { x: 0, y: 0, width: page.width, height: Math.min(h, 12000), scale: 1 }
      }
      const res = await send('Page.captureScreenshot', { format: 'png', ...(clip ? { clip } : {}) })
      writeFileSync(out, Buffer.from(res.result.data, 'base64'))
      if (full) await page.viewport(page.width, page.height, page.mobile)
      return out
    },
    async close() {
      try {
        ws.close()
      } catch {}
      // On Windows killing chrome.exe leaves its renderers running; end the tree.
      if (process.platform === 'win32') spawn('taskkill', ['/pid', String(proc.pid), '/T', '/F'], { stdio: 'ignore' })
      else proc.kill()
    },
  }
  await page.viewport(width, height, mobile)
  return page
}
