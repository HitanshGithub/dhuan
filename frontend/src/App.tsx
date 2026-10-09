import { Code2, Flame, History, Info, Radio } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { api, dataRoot, frameImage, reverseName, type Place, type PointForecast, type Replay, type RunMeta } from './api'
import About from './components/About'
import Legend from './components/Legend'
import PlacePanel from './components/PlacePanel'
import Search from './components/Search'
import SmokeMap from './components/SmokeMap'
import Timeline from './components/Timeline'
import { formatCount, istDay, istTime } from './format'

const REPO = 'https://github.com/HitanshGithub/dhuan'

export default function App() {
  const [liveMeta, setLiveMeta] = useState<RunMeta | null>(null)
  const [meta, setMeta] = useState<RunMeta | null>(null)
  const [replays, setReplays] = useState<Replay[]>([])
  const [metaError, setMetaError] = useState<string | null>(null)
  const [frame, setFrame] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [place, setPlace] = useState<Place | null>(null)
  const [forecast, setForecast] = useState<PointForecast | null>(null)
  const [fcLoading, setFcLoading] = useState(false)
  const [fcError, setFcError] = useState<string | null>(null)
  const [about, setAbout] = useState(false)
  const [showStations, setShowStations] = useState(true)

  const isReplay = !!meta?.replay
  const runParam = isReplay ? meta?.run_id : undefined

  // a shared link opens straight on its place: ?lat=..&lon=..&name=..
  useEffect(() => {
    const q = new URLSearchParams(window.location.search)
    const lat = Number(q.get('lat'))
    const lon = Number(q.get('lon'))
    if (Number.isFinite(lat) && Number.isFinite(lon) && q.has('lat') && q.has('lon')) {
      setPlace({ name: q.get('name') || `${lat.toFixed(2)}°N, ${lon.toFixed(2)}°E`, lat, lon })
    }
  }, [])
  useEffect(() => {
    const url = place ? `?lat=${place.lat.toFixed(4)}&lon=${place.lon.toFixed(4)}&name=${encodeURIComponent(place.name)}` : window.location.pathname
    window.history.replaceState(null, '', url)
  }, [place])

  // warm the browser cache with a run's frames, nearest hours first
  const preload = useCallback((m: RunMeta) => {
    const order = [...m.times.keys()].sort((a, b) => Math.abs(a - m.now_frame) - Math.abs(b - m.now_frame))
    let i = 0
    const next = () => {
      if (i >= order.length) return
      const img = new Image()
      img.crossOrigin = 'anonymous' // same request mode as MapLibre's fetch, so the cached copy carries CORS headers
      img.onload = img.onerror = () => {
        i += 1
        next()
      }
      img.src = frameImage(m, order[i])
    }
    next()
    next()
  }, [])

  // the latest run, and the list of replays
  useEffect(() => {
    api
      .latest()
      .then((m) => {
        setLiveMeta(m)
        setMeta(m)
        setFrame(m.now_frame)
        preload(m)
      })
      .catch((e: Error) => setMetaError(e.message))
    api.replays().then(setReplays)
  }, [preload])

  const selectRun = async (runId: 'live' | string) => {
    if (!liveMeta) return
    setPlaying(false)
    if (runId === 'live') {
      setMeta(liveMeta)
      setFrame(liveMeta.now_frame)
      return
    }
    try {
      const m = await api.runMeta(dataRoot(liveMeta), runId)
      setMeta(m)
      setFrame(m.now_frame)
      preload(m)
    } catch (e) {
      setMetaError((e as Error).message)
    }
  }

  // playback
  useEffect(() => {
    if (!playing || !meta) return
    const id = window.setInterval(() => setFrame((f) => (f + 1 >= meta.times.length ? meta.now_frame : f + 1)), 240)
    return () => window.clearInterval(id)
  }, [playing, meta])

  // a tap on the map
  const pick = useCallback((lat: number, lon: number) => {
    const fallback = `${lat.toFixed(2)}°N, ${lon.toFixed(2)}°E`
    setPlace({ name: fallback, lat, lon })
    reverseName(lat, lon).then((name) => name && setPlace((p) => (p && p.lat === lat && p.lon === lon ? { ...p, name } : p)))
  }, [])

  // the forecast for the chosen place, from the run being shown
  useEffect(() => {
    if (!place) {
      setForecast(null)
      setFcError(null)
      return
    }
    let cancelled = false
    setFcLoading(true)
    setFcError(null)
    api
      .forecast(place.lat, place.lon, runParam)
      .then((fc) => !cancelled && setForecast(fc))
      .catch((e: Error) => !cancelled && setFcError(e.message))
      .finally(() => !cancelled && setFcLoading(false))
    return () => {
      cancelled = true
    }
  }, [place?.lat, place?.lon, runParam]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="relative h-full w-full overflow-hidden bg-ink">
      <SmokeMap meta={meta} frame={frame} place={place} onPick={pick} showStations={showStations} />

      {/* header */}
      <div className="absolute left-3 top-3 z-10 w-[min(400px,calc(100%-24px))] md:left-4 md:top-4">
        <div className="glass rounded-2xl p-3 shadow-2xl md:p-4">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-baseline gap-2">
              <Flame className="translate-y-1 text-ember" size={22} />
              <span className="font-display text-2xl font-bold tracking-tight">Dhuan</span>
              <span className="font-display text-lg text-mist/70">धुआं</span>
            </div>
            <div className="flex items-center gap-1">
              <button onClick={() => setAbout(true)} className="rounded-full p-1.5 text-mist hover:bg-white/10 hover:text-white" aria-label="How it works" title="How it works">
                <Info size={18} />
              </button>
              <a href={REPO} target="_blank" rel="noreferrer" className="rounded-full p-1.5 text-mist hover:bg-white/10 hover:text-white" aria-label="Source on GitHub" title="Source on GitHub">
                <Code2 size={18} />
              </a>
            </div>
          </div>
          {/* on a phone with a place open, keep only the brand row so the map stays visible */}
          <div className={place ? 'hidden md:block' : ''}>
            <p className="mt-1 text-sm leading-snug text-mist">Where North India's farm-fire smoke is going, when it reaches you, and from where.</p>
            {meta && !isReplay && (
              <div className="mt-2 flex items-center gap-2 text-xs text-mist/80">
                <span className="pulse relative inline-block h-2 w-2 rounded-full bg-emerald-400" />
                Live · {formatCount(meta.fires.count)} fires seen in the last 48 h · updated {istTime(meta.generated_at)} IST
              </div>
            )}
            {meta && isReplay && (
              <div className="mt-2 flex items-center gap-2 text-xs text-amber-200">
                <History size={13} />
                Replay · {istDay(meta.times[meta.now_frame])} · {formatCount(meta.fires.count)} fires in 48 h · archived fires and winds, same model
              </div>
            )}
            {metaError && <div className="mt-2 rounded-lg bg-red-500/10 px-2 py-1 text-xs text-red-200">No forecast yet: {metaError}</div>}
            {replays.length > 0 && liveMeta && (
              <div className="mt-2 flex rounded-full bg-white/5 p-0.5 text-xs ring-1 ring-line">
                <button
                  onClick={() => selectRun('live')}
                  className={`flex flex-1 items-center justify-center gap-1 rounded-full px-2 py-1 transition ${!isReplay ? 'bg-ember font-semibold text-ink' : 'text-mist hover:text-white'}`}
                >
                  <Radio size={12} /> Live
                </button>
                {replays.slice(0, 2).map((r) => (
                  <button
                    key={r.run_id}
                    onClick={() => selectRun(r.run_id)}
                    className={`flex flex-1 items-center justify-center gap-1 rounded-full px-2 py-1 transition ${meta?.run_id === r.run_id ? 'bg-amber-300 font-semibold text-ink' : 'text-mist hover:text-white'}`}
                    title={r.title}
                  >
                    <History size={12} /> {istDay(`${r.date}T12:00:00Z`)}
                  </button>
                ))}
              </div>
            )}
            <div className="mt-3">
              <Search onPlace={setPlace} />
            </div>
            <p className="mt-2 text-[11px] text-mist/60">Or tap anywhere on the map.</p>
          </div>
        </div>
      </div>

      {/* legend (desktop, when the panel is closed) */}
      {meta && !place && (
        <div className="absolute right-4 top-4 z-10 hidden md:block">
          <Legend meta={meta} showStations={showStations} onToggleStations={() => setShowStations((s) => !s)} />
        </div>
      )}

      {/* place panel: right card on desktop, bottom sheet on phones */}
      {place && (
        <div className="absolute inset-x-0 bottom-0 z-20 h-[50vh] p-2 md:inset-x-auto md:bottom-36 md:right-4 md:top-4 md:h-auto md:w-[400px] md:p-0">
          <PlacePanel place={place} forecast={forecast} loading={fcLoading} error={fcError} frame={frame} run={runParam} onFrame={setFrame} onClose={() => setPlace(null)} />
        </div>
      )}

      {/* timeline */}
      {meta && (
        <div
          className={`absolute z-10 left-1/2 w-[min(760px,calc(100%-16px))] -translate-x-1/2 transition-all ${
            place ? 'bottom-[calc(50vh+8px)] md:bottom-4 md:left-4 md:w-[min(760px,calc(100%-440px))] md:translate-x-0' : 'bottom-3 md:bottom-4'
          }`}
        >
          <Timeline meta={meta} frame={frame} playing={playing} onFrame={setFrame} onPlay={setPlaying} />
          {!place && (
            <div className="mt-2 md:hidden">
              <Legend meta={meta} showStations={showStations} onToggleStations={() => setShowStations((s) => !s)} />
            </div>
          )}
        </div>
      )}

      {about && <About meta={meta} onClose={() => setAbout(false)} />}
    </div>
  )
}
