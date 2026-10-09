// Headless screenshots of the running app (dev server on :5173 by default), using the installed Chrome.
// Usage: node scripts/screenshots.mjs [baseUrl]
import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'

const base = process.argv[2] ?? 'http://localhost:5173'
const out = new URL('../screenshots/', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')
mkdirSync(out, { recursive: true })

const browser = await chromium.launch({ channel: 'chrome', headless: true, args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] })

async function shoot(name, { width, height, mobile = false, steps = async () => {} }) {
  const context = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: mobile ? 2 : 1, isMobile: mobile, hasTouch: mobile })
  const page = await context.newPage()
  page.on('pageerror', (e) => console.error(`[${name}] page error:`, e.message))
  page.on('console', (m) => m.type() === 'error' && console.error(`[${name}] console:`, m.text()))
  await page.goto(base, { waitUntil: 'load' })
  await page.waitForSelector('text=Live', { timeout: 30000 })
  await page.waitForTimeout(6000) // tiles, fonts and the first frame in a cold context
  await steps(page)
  await page.screenshot({ path: `${out}${name}.png` })
  console.log('saved', `${name}.png`)
  await context.close()
}

await shoot('01-home-desktop', { width: 1440, height: 900 })
await shoot('02-place-desktop', {
  width: 1440,
  height: 900,
  steps: async (page) => {
    await page.getByRole('button', { name: 'Delhi', exact: true }).click()
    await page.waitForSelector('text=Right now', { timeout: 20000 })
    await page.waitForTimeout(1500)
  },
})
await shoot('03-forecast-desktop', {
  width: 1440,
  height: 900,
  steps: async (page) => {
    await page.getByRole('button', { name: 'Ludhiana', exact: true }).click()
    await page.waitForSelector('text=Right now', { timeout: 20000 })
    const slider = page.getByLabel('Forecast hour')
    await slider.focus()
    for (let i = 0; i < 20; i++) await page.keyboard.press('ArrowRight')
    await page.waitForTimeout(1500)
  },
})
await shoot('04-about-desktop', {
  width: 1440,
  height: 900,
  steps: async (page) => {
    await page.getByRole('button', { name: 'How it works' }).click()
    await page.waitForTimeout(500)
  },
})
await shoot('07-replay-desktop', {
  width: 1440,
  height: 900,
  steps: async (page) => {
    const replay = page.getByRole('button', { name: /Nov/ }).first()
    if ((await replay.count()) === 0) return
    await replay.click()
    await page.waitForTimeout(2500)
    await page.getByRole('button', { name: 'Delhi', exact: true }).click()
    await page.waitForSelector('text=Replay of', { timeout: 20000 })
    const slider = page.getByLabel('Forecast hour')
    await slider.focus()
    for (let i = 0; i < 14; i++) await page.keyboard.press('ArrowRight')
    await page.waitForTimeout(2500)
  },
})
await shoot('05-home-mobile', { width: 390, height: 844, mobile: true })
await shoot('06-place-mobile', {
  width: 390,
  height: 844,
  mobile: true,
  steps: async (page) => {
    await page.getByRole('button', { name: 'Delhi', exact: true }).click()
    await page.waitForSelector('text=Right now', { timeout: 20000 })
    await page.waitForTimeout(1500)
  },
})

await browser.close()
