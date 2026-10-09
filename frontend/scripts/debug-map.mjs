// Why is the map blank? Log every console message, page error and map-related network response.
import { chromium } from 'playwright'

const base = process.argv[2] ?? 'http://localhost:5173'
const browser = await chromium.launch({ channel: 'chrome', headless: true, args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] })
const page = await browser.newPage({ viewport: { width: 1200, height: 800 } })
page.on('console', (m) => console.log(`[console.${m.type()}]`, m.text().slice(0, 300)))
page.on('pageerror', (e) => console.log('[pageerror]', e.message.slice(0, 300)))
page.on('response', (r) => {
  const u = r.url()
  if (/openfreemap|\/data\/|maplibre|\/api\//.test(u)) console.log(`[net ${r.status()}]`, u.slice(0, 140))
})
await page.goto(base, { waitUntil: 'networkidle' })
await page.waitForTimeout(6000)
const info = await page.evaluate(() => {
  const c = document.querySelector('canvas.maplibregl-canvas')
  const test = document.createElement('canvas')
  return {
    canvas: !!c,
    size: c ? [c.width, c.height] : null,
    webgl2: !!test.getContext('webgl2'),
    webgl: !!test.getContext('webgl'),
    layers: document.querySelectorAll('.maplibregl-canvas-container').length,
  }
})
console.log(info)
await page.screenshot({ path: 'screenshots/debug.png' })
await browser.close()
