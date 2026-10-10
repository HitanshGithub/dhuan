import { useEffect, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import type { ImageSource, Map as MLMap, MapMouseEvent } from 'maplibre-gl'
import { dataUrl, frameImage, type Place, type RunMeta } from '../api'
import WindCanvas, { type WindData } from './WindCanvas'

// OpenFreeMap's dark style, served from this site with its Natural Earth relief raster removed: that source's tiles
// started returning 404 on 10 Oct 2026 and MapLibre never finished loading while it failed. Tiles, glyphs and sprites
// still come from OpenFreeMap.
const STYLE = `${import.meta.env.BASE_URL}styles/dark.json`
// MapLibre 6 looks for its worker next to its own module URL, which Vite rewrites; serve it from /public instead
maplibregl.setWorkerUrl(`${import.meta.env.BASE_URL}maplibre/maplibre-gl-worker.mjs`)

interface Props {
  meta: RunMeta | null
  frame: number
  place: Place | null
  onPick: (lat: number, lon: number) => void
  showStations: boolean
  onFail?: (message: string) => void
  onReady?: () => void
}

export default function SmokeMap({ meta, frame, place, onPick, showStations, onFail, onReady }: Props) {
  const container = useRef<HTMLDivElement>(null)
  const map = useRef<MLMap | null>(null)
  const marker = useRef<maplibregl.Marker | null>(null)
  const ready = useRef(false)
  const pick = useRef(onPick)
  pick.current = onPick
  const [mapObj, setMapObj] = useState<MLMap | null>(null)
  const [wind, setWind] = useState<WindData | null>(null)

  // the wind field that carried the smoke, for the animated streaks (older runs may not have it)
  useEffect(() => {
    if (!meta) return
    let cancelled = false
    fetch(dataUrl(meta, 'winds.json'))
      .then((r) => (r.ok ? r.json() : null))
      .then((w) => !cancelled && setWind(w))
      .catch(() => !cancelled && setWind(null))
    return () => {
      cancelled = true
    }
  }, [meta])

  // the map itself, once
  useEffect(() => {
    if (!container.current || map.current) return
    let m: MLMap
    try {
      m = new maplibregl.Map({
        container: container.current,
        style: STYLE,
        center: [77.2, 28.3],
        zoom: 5.3,
        minZoom: 4,
        maxZoom: 11,
        attributionControl: false,
      })
    } catch (e) {
      // almost always WebGL being unavailable: graphics acceleration off, a blocklisted GPU, or a remote desktop
      onFail?.(`The map needs WebGL, which this browser could not start (${(e as Error).message}). In Chrome, open chrome://settings/system and turn on "Use graphics acceleration when available", then relaunch; or try another browser.`)
      return
    }
    m.on('error', (e) => {
      const msg = e.error?.message ?? ''
      if (/webgl|context/i.test(msg)) onFail?.(`The map's graphics context failed: ${msg}`)
    })
    m.getCanvas().addEventListener('webglcontextlost', () => onFail?.('The browser lost the map’s graphics context (this happens when the GPU is overloaded or the tab was suspended). Reload the page to restore the map.'))
    m.addControl(new maplibregl.AttributionControl({ compact: true, customAttribution: 'Fires: NASA FIRMS · Winds: Open-Meteo · Map: OpenFreeMap, OpenStreetMap' }), 'bottom-right')
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-left')
    m.on('click', (e: MapMouseEvent) => pick.current(e.lngLat.lat, e.lngLat.lng))
    // 'style.load' fires as soon as the style JSON is parsed; 'load' would also wait for every basemap tile, and a
    // slow tile server must not keep the smoke and the fires off the screen
    m.once('style.load', () => {
      ready.current = true
      m.getCanvas().style.cursor = 'crosshair'
      setMapObj(m)
      onReady?.()
    })
    // browsers pause animation frames for hidden or occluded windows, and the first frame may never come:
    // nudge the renderer when the page becomes visible, and say something if it still has not drawn
    const nudge = () => {
      if (!ready.current && document.visibilityState === 'visible') {
        m.resize()
        m.triggerRepaint()
      }
    }
    document.addEventListener('visibilitychange', nudge)
    const watchdog = window.setTimeout(() => {
      nudge()
      window.setTimeout(() => {
        if (!ready.current && document.visibilityState === 'visible') {
          onFail?.('The map is taking long to draw. On a slow connection give it a moment; if it stays black, your browser may have graphics acceleration turned off: in Chrome open chrome://settings/system, turn on "Use graphics acceleration when available", relaunch, and reload this page.')
        }
      }, 8000)
    }, 8000)
    map.current = m
    return () => {
      document.removeEventListener('visibilitychange', nudge)
      window.clearTimeout(watchdog)
      m.remove()
      map.current = null
      ready.current = false
      setMapObj(null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // smoke overlay + fires, whenever a run is loaded
  useEffect(() => {
    const m = map.current
    if (!m || !meta) return
    const install = () => {
      const corners = meta.bounds as [[number, number], [number, number], [number, number], [number, number]]
      const firstSymbol = m.getStyle().layers.find((l) => l.type === 'symbol')?.id
      if (m.getSource('smoke')) {
        ;(m.getSource('smoke') as ImageSource).updateImage({ url: frameImage(meta, frame), coordinates: corners })
      } else {
        m.addSource('smoke', { type: 'image', url: frameImage(meta, frame), coordinates: corners })
        m.addLayer(
          { id: 'smoke', type: 'raster', source: 'smoke', paint: { 'raster-opacity': 0.88, 'raster-fade-duration': 0, 'raster-resampling': 'linear' } },
          firstSymbol,
        )
      }
      if (m.getSource('fires')) {
        ;(m.getSource('fires') as maplibregl.GeoJSONSource).setData(dataUrl(meta, 'fires.geojson'))
      } else {
        m.addSource('fires', { type: 'geojson', data: dataUrl(meta, 'fires.geojson') })
        m.addLayer(
          {
            id: 'fires-glow',
            type: 'circle',
            source: 'fires',
            paint: {
              'circle-radius': ['interpolate', ['linear'], ['get', 'frp'], 1, 6, 40, 14, 80, 20],
              'circle-color': '#ff6a00',
              'circle-blur': 1,
              'circle-opacity': 0.45,
            },
          },
          firstSymbol,
        )
        m.addLayer(
          {
            id: 'fires',
            type: 'circle',
            source: 'fires',
            paint: {
              'circle-radius': ['interpolate', ['linear'], ['get', 'frp'], 1, 2, 40, 4.5, 80, 6],
              'circle-color': '#ffd166',
              'circle-stroke-color': '#ff6a00',
              'circle-stroke-width': 1,
              'circle-opacity': 0.95,
            },
          },
          firstSymbol,
        )
        const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 10 })
        m.on('mouseenter', 'fires', (e) => {
          const f = e.features?.[0]
          if (!f) return
          const p = f.properties as { frp: number; time: string; district: string | null; satellites: string; detections: number }
          const when = new Date(p.time).toLocaleString('en-IN', { weekday: 'short', hour: 'numeric', minute: '2-digit', hour12: true, timeZone: 'Asia/Kolkata' })
          popup
            .setLngLat((f.geometry as { coordinates: [number, number] }).coordinates)
            .setHTML(
              `<div style="font-weight:600">${p.district ?? 'Fire'}</div><div style="color:#aab6c5">${when} IST · ${p.frp} MW · ${p.satellites}</div>`,
            )
            .addTo(m)
        })
        m.on('mouseleave', 'fires', () => popup.remove())
      }
      // measured AQI at monitoring stations, when the run has them
      const empty = { type: 'FeatureCollection' as const, features: [] as never[] }
      const stationsData = meta.has_stations ? dataUrl(meta, 'stations.geojson') : empty
      if (m.getSource('stations')) {
        ;(m.getSource('stations') as maplibregl.GeoJSONSource).setData(stationsData)
      } else {
        m.addSource('stations', { type: 'geojson', data: stationsData })
        m.addLayer(
          {
            id: 'stations',
            type: 'circle',
            source: 'stations',
            paint: {
              'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 3.5, 8, 7],
              'circle-color': ['get', 'color'],
              'circle-stroke-color': 'rgba(255,255,255,0.85)',
              'circle-stroke-width': 1.2,
              'circle-opacity': 0.95,
            },
          },
          firstSymbol,
        )
        const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 10 })
        m.on('mouseenter', 'stations', (e) => {
          const f = e.features?.[0]
          if (!f) return
          const p = f.properties as { name: string; aqi: number; pm25: number | null; time: string; label: string }
          const when = p.time ? new Date(p.time).toLocaleTimeString('en-IN', { hour: 'numeric', hour12: true, timeZone: 'Asia/Kolkata' }) : ''
          popup
            .setLngLat((f.geometry as { coordinates: [number, number] }).coordinates)
            .setHTML(
              `<div style="font-weight:600">${p.name}</div><div style="color:#aab6c5">Measured AQI ${p.aqi} · ${p.label}${p.pm25 != null ? ` · ≈${p.pm25} µg/m³ PM2.5` : ''}${when ? ` · ${when} IST` : ''}</div>`,
            )
            .addTo(m)
        })
        m.on('mouseleave', 'stations', () => popup.remove())
      }
      m.setLayoutProperty('stations', 'visibility', showStations ? 'visible' : 'none')
    }
    if (ready.current) install()
    else m.once('style.load', install)
    // frame and the stations toggle are handled by the next effects; this one only runs when the run changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [meta])

  // stations on/off
  useEffect(() => {
    const m = map.current
    if (!m || !ready.current || !m.getLayer('stations')) return
    m.setLayoutProperty('stations', 'visibility', showStations ? 'visible' : 'none')
  }, [showStations])

  // swap the frame image
  useEffect(() => {
    const m = map.current
    if (!m || !meta || !ready.current) return
    const src = m.getSource('smoke') as ImageSource | undefined
    src?.updateImage({ url: frameImage(meta, frame) })
  }, [meta, frame])

  // the chosen place
  useEffect(() => {
    const m = map.current
    if (!m) return
    marker.current?.remove()
    marker.current = null
    if (!place) return
    const el = document.createElement('div')
    el.className = 'dhuan-pin'
    marker.current = new maplibregl.Marker({ element: el, anchor: 'bottom' }).setLngLat([place.lon, place.lat]).addTo(m)
    const padding = window.innerWidth >= 768 ? { right: 420, left: 40, top: 80, bottom: 140 } : { top: 120, bottom: window.innerHeight * 0.55, left: 20, right: 20 }
    m.easeTo({ center: [place.lon, place.lat], zoom: Math.max(m.getZoom(), 6.2), padding, duration: 900 })
  }, [place])

  // the wrapper is positioned; the inner div is the map container, whose position MapLibre's CSS sets to relative
  return (
    <div className="absolute inset-0">
      <div ref={container} className="h-full w-full" aria-label="Map of North India with smoke forecast" />
      <WindCanvas map={mapObj} wind={wind} frame={frame} />
    </div>
  )
}
