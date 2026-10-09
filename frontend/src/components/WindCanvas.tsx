import { useEffect, useRef } from 'react'
import type { Map as MLMap } from 'maplibre-gl'

export interface WindData {
  lats: number[] // ascending, 1-degree grid
  lons: number[]
  u: number[][] // [frame][lat * nlon + lon], m/s eastward
  v: number[][]
}

interface Props {
  map: MLMap | null
  wind: WindData | null
  frame: number
}

const COUNT = 1400
const MAX_AGE = 90
const STEP = 0.00045 // degrees per m/s per tick: exaggerated on purpose, this is a picture of the flow, not a measurement

/** Streaks drifting with the 100 m wind of the current frame, drawn on a canvas over the map (windy.com style). */
export default function WindCanvas({ map, wind, frame }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const frameRef = useRef(frame)
  const windRef = useRef(wind)
  frameRef.current = frame
  windRef.current = wind

  useEffect(() => {
    const c = canvas.current
    if (!map || !c) return
    const ctx = c.getContext('2d')
    if (!ctx) return
    let raf = 0
    let alive = true
    const dpr = Math.min(window.devicePixelRatio || 1, 2)

    const fit = () => {
      const { clientWidth: w, clientHeight: h } = map.getContainer()
      c.width = w * dpr
      c.height = h * dpr
      c.style.width = `${w}px`
      c.style.height = `${h}px`
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }
    fit()

    type P = { lon: number; lat: number; age: number; x: number; y: number }
    const particles: P[] = []
    const spawn = (p?: P): P => {
      const b = map.getBounds()
      const w = windRef.current
      const lon0 = Math.max(b.getWest(), w ? w.lons[0] : -180)
      const lon1 = Math.min(b.getEast(), w ? w.lons[w.lons.length - 1] : 180)
      const lat0 = Math.max(b.getSouth(), w ? w.lats[0] : -90)
      const lat1 = Math.min(b.getNorth(), w ? w.lats[w.lats.length - 1] : 90)
      const lon = lon0 + Math.random() * Math.max(lon1 - lon0, 0.01)
      const lat = lat0 + Math.random() * Math.max(lat1 - lat0, 0.01)
      const pt = map.project([lon, lat])
      const q = p ?? ({} as P)
      q.lon = lon
      q.lat = lat
      q.age = Math.floor(Math.random() * MAX_AGE)
      q.x = pt.x
      q.y = pt.y
      return q
    }
    for (let i = 0; i < COUNT; i++) particles.push(spawn())

    const sample = (lon: number, lat: number): [number, number] | null => {
      const w = windRef.current
      if (!w) return null
      const f = Math.min(frameRef.current, w.u.length - 1)
      const nlon = w.lons.length
      const fx = (lon - w.lons[0]) / (w.lons[1] - w.lons[0])
      const fy = (lat - w.lats[0]) / (w.lats[1] - w.lats[0])
      if (fx < 0 || fy < 0 || fx >= nlon - 1 || fy >= w.lats.length - 1) return null
      const ix = Math.floor(fx)
      const iy = Math.floor(fy)
      const tx = fx - ix
      const ty = fy - iy
      const at = (a: number[], j: number, i: number) => a[j * nlon + i]
      const bil = (a: number[]) =>
        at(a, iy, ix) * (1 - tx) * (1 - ty) + at(a, iy, ix + 1) * tx * (1 - ty) + at(a, iy + 1, ix) * (1 - tx) * ty + at(a, iy + 1, ix + 1) * tx * ty
      return [bil(w.u[f]), bil(w.v[f])]
    }

    const tick = () => {
      if (!alive) return
      const w = c.width / dpr
      const h = c.height / dpr
      // fade what is already there, so each streak leaves a short tail
      ctx.globalCompositeOperation = 'destination-out'
      ctx.fillStyle = 'rgba(0,0,0,0.12)'
      ctx.fillRect(0, 0, w, h)
      ctx.globalCompositeOperation = 'source-over'
      ctx.lineWidth = 1.1
      ctx.lineCap = 'round'
      if (windRef.current) {
        ctx.beginPath()
        for (const p of particles) {
          const uv = sample(p.lon, p.lat)
          if (!uv || p.age++ > MAX_AGE) {
            spawn(p)
            continue
          }
          const [u, v] = uv
          p.lon += (u * STEP) / Math.cos((p.lat * Math.PI) / 180)
          p.lat += v * STEP
          const pt = map.project([p.lon, p.lat])
          if (pt.x < -10 || pt.y < -10 || pt.x > w + 10 || pt.y > h + 10) {
            spawn(p)
            continue
          }
          ctx.moveTo(p.x, p.y)
          ctx.lineTo(pt.x, pt.y)
          p.x = pt.x
          p.y = pt.y
        }
        ctx.strokeStyle = 'rgba(205, 220, 245, 0.42)'
        ctx.stroke()
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)

    const onMove = () => {
      ctx.clearRect(0, 0, c.width, c.height)
      for (const p of particles) {
        const pt = map.project([p.lon, p.lat])
        p.x = pt.x
        p.y = pt.y
      }
    }
    const onMoveEnd = () => {
      for (const p of particles) spawn(p)
      ctx.clearRect(0, 0, c.width, c.height)
    }
    map.on('move', onMove)
    map.on('moveend', onMoveEnd)
    map.on('resize', fit)
    return () => {
      alive = false
      cancelAnimationFrame(raf)
      map.off('move', onMove)
      map.off('moveend', onMoveEnd)
      map.off('resize', fit)
    }
  }, [map])

  return <canvas ref={canvas} className="pointer-events-none absolute inset-0" aria-hidden="true" />
}
