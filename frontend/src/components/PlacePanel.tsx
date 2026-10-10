import { Bell, Check, Link2, Loader2, Mail, Send, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api, type Advisory, type Place, type PointForecast } from '../api'
import { BAND_COLOR, istTime, newIstDay, relativeDay } from '../format'

interface Props {
  place: Place
  forecast: PointForecast | null
  loading: boolean
  error: string | null
  frame: number
  run?: string
  onFrame: (f: number) => void
  onClose: () => void
}

const LANGS: { key: 'en' | 'hi' | 'pa'; label: string }[] = [
  { key: 'en', label: 'English' },
  { key: 'hi', label: 'हिंदी' },
  { key: 'pa', label: 'ਪੰਜਾਬੀ' },
]

export default function PlacePanel({ place, forecast, loading, error, frame, run, onFrame, onClose }: Props) {
  const [lang, setLang] = useState<'en' | 'hi' | 'pa'>('en')
  const [advisory, setAdvisory] = useState<Advisory | null>(null)
  const [advLoading, setAdvLoading] = useState(false)
  const [copied, setCopied] = useState(false)

  const share = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1800)
    } catch {
      /* clipboard blocked: the URL bar already has the link */
    }
  }

  useEffect(() => {
    if (!forecast) return
    let cancelled = false
    setAdvLoading(true)
    api
      .advisory(place.lat, place.lon, lang, place.name, run)
      .then((a) => !cancelled && setAdvisory(a))
      .catch(() => !cancelled && setAdvisory(null))
      .finally(() => !cancelled && setAdvLoading(false))
    return () => {
      cancelled = true
    }
  }, [forecast, lang, place, run])

  return (
    <div className="glass flex h-full flex-col rounded-2xl shadow-2xl">
      <div className="flex items-start justify-between gap-3 px-4 pt-4">
        <div className="min-w-0">
          <div className="truncate font-display text-lg font-semibold">{place.name}</div>
          <div className="text-xs text-mist/70">
            {place.lat.toFixed(2)}°N, {place.lon.toFixed(2)}°E
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <button onClick={share} title="Copy a link to this place" aria-label="Copy a link to this place" className="flex items-center gap-1 rounded-full px-2 py-1 text-xs text-mist/70 hover:bg-white/10 hover:text-white">
            {copied ? <Check size={14} className="text-emerald-300" /> : <Link2 size={14} />}
            {copied ? 'Copied' : 'Share'}
          </button>
          <button onClick={onClose} aria-label="Close" className="rounded-full p-1 text-mist/70 hover:bg-white/10 hover:text-white">
            <X size={18} />
          </button>
        </div>
      </div>

      <div className="scroll-thin min-h-0 flex-1 overflow-y-auto px-4 pb-4">
        {loading && (
          <div className="flex items-center gap-2 py-8 text-sm text-mist">
            <Loader2 className="animate-spin" size={16} /> Reading the forecast for this place…
          </div>
        )}
        {error && <div className="mt-3 rounded-xl bg-red-500/10 p-3 text-sm text-red-200 ring-1 ring-red-500/30">{error}</div>}
        {forecast && !loading && (
          <>
            <Headline fc={forecast} />
            <Chart fc={forecast} frame={frame} onFrame={onFrame} />
            <Sources fc={forecast} />
            <section className="mt-5">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-mist/70">What to do</h3>
                <div className="flex rounded-full bg-white/5 p-0.5 ring-1 ring-line">
                  {LANGS.map((l) => (
                    <button
                      key={l.key}
                      onClick={() => setLang(l.key)}
                      className={`rounded-full px-2.5 py-0.5 text-xs transition ${lang === l.key ? 'bg-ember text-ink font-semibold' : 'text-mist hover:text-white'}`}
                    >
                      {l.label}
                    </button>
                  ))}
                </div>
              </div>
              <div className="mt-2 whitespace-pre-line rounded-xl bg-white/5 p-3 text-sm leading-relaxed text-white/90 ring-1 ring-line">
                {advLoading && !advisory ? (
                  <span className="inline-flex items-center gap-2 text-mist">
                    <Loader2 className="animate-spin" size={14} /> Writing…
                  </span>
                ) : advisory ? (
                  advisory.body.replace(/\n\nhttps?:\S+$/, '')
                ) : (
                  forecast.peak.meaning
                )}
                {advisory && advisory.generated_by === 'ai' && <div className="mt-2 text-[10px] text-mist/60">Written in {LANGS.find((l) => l.key === advisory.language)?.label} by Ministral 3 on Amazon Bedrock from the forecast above.</div>}
                {advisory && advisory.generated_by === 'template' && advisory.language !== lang && (
                  <div className="mt-2 text-[10px] text-mist/60">Shown in {advisory.language === 'hi' ? 'Hindi' : 'English'}: the model is off in this build.</div>
                )}
              </div>
            </section>
            <Subscribe place={place} />
            <p className="mt-4 text-[10px] leading-snug text-mist/50">{forecast.disclaimer}</p>
          </>
        )}
      </div>
    </div>
  )
}

function Headline({ fc }: { fc: PointForecast }) {
  const nowIso = fc.now.time
  const peakAhead = fc.peak.frame > fc.frames.findIndex((f) => f.is_now)
  return (
    <div className="mt-3">
      {fc.replay && (
        <div className="mb-2 rounded-lg bg-amber-300/10 px-3 py-1.5 text-xs text-amber-100 ring-1 ring-amber-300/30">
          Replay of {fc.replay.date}: the forecast as it would have looked at 5:30 PM that day, from archived fires and winds.
        </div>
      )}
      <div className="flex items-center gap-3 rounded-xl p-3 ring-1 ring-line" style={{ background: `${fc.now.color}1f` }}>
        <span className="h-10 w-2 rounded-full" style={{ background: fc.now.color }} />
        <div>
          <div className="text-xs text-mist/70">Farm-fire smoke right now</div>
          <div className="font-display text-xl font-semibold leading-tight">
            {fc.now.label}
            <span className="ml-2 text-sm font-medium text-mist/80">~{fc.now.ug} µg/m³</span>
          </div>
        </div>
      </div>
      {fc.observed && (
        <div className="mt-2 flex items-start gap-2 rounded-xl bg-white/5 px-3 py-2 text-xs text-mist ring-1 ring-line">
          <span className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full border border-white/70" style={{ background: fc.observed.color }} />
          <span>
            Measured now at {fc.observed.name} ({fc.observed.distance_km} km away): <span className="font-semibold text-white">AQI {fc.observed.aqi}</span>, {fc.observed.category}
            {fc.observed.pm25 != null && <> · ≈{fc.observed.pm25} µg/m³ PM2.5 from all sources</>}. The figure above is only the farm-fire share.
          </span>
        </div>
      )}
      <div className="mt-3 flex flex-wrap gap-2 text-sm [&>*]:min-w-[45%] [&>*]:flex-1">
        {fc.arrival && (
          <Moment label="Arrives" iso={fc.arrival.time} nowIso={nowIso} />
        )}
        <Moment
          label={fc.peak.key === 'clear' ? 'Highest' : peakAhead ? 'Peaks' : 'Peak was'}
          iso={fc.peak.time}
          nowIso={nowIso}
          sub={`${fc.peak.label} · ~${fc.peak.ug} µg/m³`}
          color={fc.peak.color}
        />
        {fc.clears && <Moment label="Thins out" iso={fc.clears.time} nowIso={nowIso} />}
      </div>
    </div>
  )
}

function Moment({ label, iso, nowIso, sub, color }: { label: string; iso: string; nowIso: string; sub?: string; color?: string }) {
  return (
    <div className="rounded-xl bg-white/5 p-3 ring-1 ring-line">
      <div className="text-[11px] uppercase tracking-wide text-mist/60">{label}</div>
      <div className="font-display font-semibold">
        {relativeDay(iso, nowIso)} <span className="text-mist/80">{istTime(iso)}</span>
      </div>
      {sub && (
        <div className="mt-0.5 flex items-center gap-1.5 text-xs text-mist">
          {color && <span className="h-2 w-2 rounded-full" style={{ background: color }} />}
          {sub}
        </div>
      )}
    </div>
  )
}

function Chart({ fc, frame, onFrame }: { fc: PointForecast; frame: number; onFrame: (f: number) => void }) {
  const nowI = fc.frames.findIndex((f) => f.is_now)
  const frames = fc.frames.slice(nowI)
  const max = Math.max(25, ...frames.map((f) => f.ug))
  const nowIso = fc.now.time
  const dayMarks = frames.map((f, i) => (i > 0 && newIstDay(f.time, frames[i - 1].time) ? i : -1)).filter((i) => i >= 0)
  return (
    <section className="mt-5">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-mist/70">Next 48 hours</h3>
      <div className="relative mt-2 h-28 rounded-xl bg-white/5 p-2 ring-1 ring-line">
        <div className="flex h-full items-end gap-px">
          {frames.map((f, i) => {
            const abs = nowI + i
            const active = abs === frame
            return (
              <button
                key={f.time}
                onClick={() => onFrame(abs)}
                title={`${relativeDay(f.time, nowIso)} ${istTime(f.time)} · ${f.ug} µg/m³`}
                className="group relative h-full flex-1"
                aria-label={`${istTime(f.time)}: ${f.ug}`}
              >
                <span
                  className={`absolute bottom-0 left-0 right-0 rounded-t-sm transition ${active ? 'ring-2 ring-white' : 'opacity-85 group-hover:opacity-100'}`}
                  style={{ height: `${Math.max(3, (f.ug / max) * 100)}%`, background: BAND_COLOR[f.band] }}
                />
              </button>
            )
          })}
        </div>
        {dayMarks.map((i) => (
          <span key={i} className="pointer-events-none absolute bottom-2 top-2 w-px bg-white/15" style={{ left: `calc(${(i / frames.length) * 100}% + 8px)` }} />
        ))}
      </div>
      <div className="relative mt-1 h-4 text-[10px] text-mist/60">
        {(dayMarks.length === 0 || dayMarks[0] / frames.length > 0.14) && <span className="absolute left-0">now</span>}
        {dayMarks.map((i) => (
          <span key={i} className="absolute -translate-x-1/2" style={{ left: `calc(${(i / frames.length) * 100}% + 8px)` }}>
            {relativeDay(frames[i].time, nowIso)}
          </span>
        ))}
        <span className="absolute right-0">+48 h</span>
      </div>
    </section>
  )
}

function Sources({ fc }: { fc: PointForecast }) {
  if (!fc.sources.length) return null
  return (
    <section className="mt-5">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-mist/70">Where it comes from (next 24 h)</h3>
      <ul className="mt-2 space-y-1.5">
        {fc.sources.map((s) => (
          <li key={s.district} className="text-sm">
            <div className="flex justify-between">
              <span className="truncate">{s.district}</span>
              <span className="ml-2 shrink-0 text-mist/80">{Math.round(s.share * 100)}%</span>
            </div>
            <div className="mt-0.5 h-1.5 rounded-full bg-white/5">
              <div className="h-full rounded-full bg-ember" style={{ width: `${Math.max(2, s.share * 100)}%` }} />
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}

function Subscribe({ place }: { place: Place }) {
  const [email, setEmail] = useState('')
  const [language, setLanguage] = useState<'en' | 'hi' | 'pa'>('en')
  const [state, setState] = useState<'idle' | 'busy' | 'done' | 'error'>('idle')
  const [result, setResult] = useState<{ id: string; status: string; note: string } | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [err, setErr] = useState('')

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setState('busy')
    try {
      const r = await api.subscribe({ email, lat: place.lat, lon: place.lon, label: place.name, language })
      setResult(r)
      setState('done')
    } catch (ex) {
      setErr((ex as Error).message)
      setState('error')
    }
  }

  const sendNow = async () => {
    if (!result) return
    setPreview('Sending…')
    try {
      const r = await api.preview(result.id)
      setPreview(r.sent ? `Sent to your inbox: "${r.subject}". Check spam if it is not there in a minute.` : (r.reason ?? 'Could not send'))
    } catch (ex) {
      setPreview((ex as Error).message)
    }
  }

  return (
    <section className="mt-5 rounded-xl bg-ember/10 p-3 ring-1 ring-ember/30">
      <div className="flex items-center gap-2 font-display text-sm font-semibold">
        <Bell size={15} className="text-ember" /> Get a day's notice by email
      </div>
      {state !== 'done' ? (
        <form onSubmit={submit} className="mt-2 space-y-2">
          <div className="flex items-center gap-2 rounded-lg bg-ink/60 px-3 py-2 ring-1 ring-line focus-within:ring-ember/70">
            <Mail size={14} className="text-mist/60" />
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full bg-transparent text-sm outline-none placeholder:text-mist/40"
            />
          </div>
          <div className="flex items-center gap-2">
            <select value={language} onChange={(e) => setLanguage(e.target.value as 'en' | 'hi' | 'pa')} className="rounded-lg bg-ink/60 px-2 py-2 text-sm ring-1 ring-line outline-none">
              {LANGS.map((l) => (
                <option key={l.key} value={l.key}>
                  {l.label}
                </option>
              ))}
            </select>
            <button type="submit" disabled={state === 'busy'} className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-ember px-3 py-2 text-sm font-semibold text-ink hover:brightness-110 disabled:opacity-60">
              {state === 'busy' ? <Loader2 className="animate-spin" size={14} /> : <Bell size={14} />} Alert me for {place.name}
            </button>
          </div>
          {state === 'error' && <div className="text-xs text-red-300">{err}</div>}
          <div className="text-[10px] text-mist/60">We email you when moderate or heavier smoke is expected within 36 hours, at most once in 18 hours. Unsubscribe from any email.</div>
        </form>
      ) : (
        <div className="mt-2 text-sm">
          <div className="flex items-start gap-2 text-emerald-200">
            <Check size={16} className="mt-0.5 shrink-0" /> <span>Subscribed for {place.name}.</span>
          </div>
          <div className="mt-1 text-xs text-mist">{result?.note}</div>
          {result?.status === 'pending_confirmation' && (
            <ol className="mt-2 list-decimal space-y-1 pl-5 text-xs text-mist">
              <li>Open the email from <span className="text-white">AWS Notifications</span> (check spam) and click <span className="text-white">Confirm subscription</span>.</li>
              <li>Then press the button below to get today's advisory right away.</li>
            </ol>
          )}
          <button onClick={sendNow} className="mt-2 inline-flex items-center gap-1.5 rounded-lg bg-white/10 px-3 py-1.5 text-xs font-medium hover:bg-white/15">
            <Send size={12} /> Send me today's advisory now
          </button>
          {preview && <div className="mt-2 text-xs text-mist">{preview}</div>}
        </div>
      )}
    </section>
  )
}
