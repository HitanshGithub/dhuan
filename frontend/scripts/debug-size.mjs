import { chromium } from 'playwright'
const browser = await chromium.launch({ channel: 'chrome', headless: true, args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] })
const page = await browser.newPage({ viewport: { width: 1200, height: 800 } })
await page.goto(process.argv[2] ?? 'http://localhost:5173', { waitUntil: 'networkidle' })
await page.waitForTimeout(4000)
console.log(await page.evaluate(() => {
  const q = (s) => document.querySelector(s)
  const h = (el) => el ? [el.clientWidth, el.clientHeight, getComputedStyle(el).height, getComputedStyle(el).position] : null
  const c = q('canvas.maplibregl-canvas')
  return { html: h(document.documentElement), body: h(document.body), root: h(q('#root')), app: h(q('#root > div')), mapdiv: h(q('[aria-label^="Map of"]')),
           canvasCss: c ? [c.style.width, c.style.height, c.width, c.height] : null, bg: getComputedStyle(document.body).backgroundColor }
}))
await browser.close()
