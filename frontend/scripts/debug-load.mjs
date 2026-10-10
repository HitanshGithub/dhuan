// Why does MapLibre's `load` never fire? Pull the Map instance out of React's fiber tree and inspect its state.
import { chromium } from 'playwright'

const base = process.argv[2] ?? 'http://localhost:5173'
const browser = await chromium.launch({ channel: 'chrome', headless: true, args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] })
const page = await browser.newPage({ viewport: { width: 1200, height: 800 } })
page.on('pageerror', (e) => console.log('[pageerror]', e.message.slice(0, 300)))
page.on('console', (m) => (m.type() === 'error' || m.type() === 'warning') && console.log(`[${m.type()}]`, m.text().slice(0, 200)))
const t0 = Date.now()
await page.goto(base, { waitUntil: 'load' })
// how long until the first fires request (our layers installed) and the first tile?
let firstTile = null
let firstFires = null
page.on('response', (r) => {
  if (!firstTile && r.url().includes('.pbf') && !r.url().includes('fonts')) firstTile = Date.now() - t0
  if (!firstFires && r.url().includes('fires.geojson')) firstFires = Date.now() - t0
})
for (let i = 0; i < 30 && !firstFires; i++) await page.waitForTimeout(1000)
console.log(`first tile after ${firstTile} ms, fires.geojson after ${firstFires} ms`)
await page.screenshot({ path: 'screenshots/debug.png' })
const info = await page.evaluate(() => {
  const el = document.querySelector('.maplibregl-map')
  if (!el) return 'no map element'
  const key = Object.keys(el).find((k) => k.startsWith('__reactFiber'))
  let f = el[key]
  let map = null
  for (let i = 0; i < 6 && f && !map; i++, f = f.return) {
    let h = f.memoizedState
    for (let j = 0; j < 12 && h; j++, h = h.next) {
      const v = h.memoizedState
      if (v && v.current && typeof v.current.getZoom === 'function') {
        map = v.current
        break
      }
    }
  }
  if (!map) return 'map not found'
  const style = map.style
  const sources = {}
  for (const [id, sc] of Object.entries(style.sourceCaches || {})) {
    const src = sc.getSource ? sc.getSource() : sc._source
    const tiles = Object.values(sc._tiles || {})
    sources[id] = { loaded: src && src.loaded ? src.loaded() : null, tiles: tiles.length, states: [...new Set(tiles.map((t) => t.state))].join(','), used: sc.used }
  }
  return {
    loaded: map.loaded(),
    styleLoaded: map.isStyleLoaded(),
    styleDirty: map._styleDirty,
    sourcesDirty: map._sourcesDirty,
    styleInnerLoaded: style.loaded ? style.loaded() : null,
    imagesLoaded: style.imageManager ? style.imageManager.isLoaded() : null,
    spriteLoaded: style._spritesImagesIds ? Object.keys(style._spritesImagesIds).length : 'n/a',
    sources,
    frame: !!map._frameRequest,
    visibility: document.visibilityState,
    canvas: [map.getCanvas().width, map.getCanvas().height],
  }
})
console.log(JSON.stringify(info, null, 1))
await browser.close()
