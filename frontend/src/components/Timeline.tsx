import { Pause, Play, RotateCcw } from 'lucide-react'
import type { RunMeta } from '../api'
import { istTime, relativeDay } from '../format'

interface Props {
  meta: RunMeta
  frame: number
  playing: boolean
  onFrame: (f: number) => void
  onPlay: (p: boolean) => void
}

export default function Timeline({ meta, frame, playing, onFrame, onPlay }: Props) {
  const n = meta.times.length
  const nowIso = meta.times[meta.now_frame]
  const iso = meta.times[frame]
  const isFuture = frame > meta.now_frame
  const isNow = frame === meta.now_frame
  // ticks at each midnight IST and at "now"
  const ticks: { at: number; label: string }[] = []
  meta.times.forEach((t, i) => {
    if (istTime(t).startsWith('12 am')) ticks.push({ at: i, label: relativeDay(t, nowIso) })
  })
  const pct = (i: number) => `${(i / (n - 1)) * 100}%`
  const assumed = isFuture && frame - meta.now_frame > 12 && meta.fires.assumed_repeat > 0

  return (
    <div className="glass rounded-2xl px-4 pt-3 pb-3 shadow-2xl">
      <div className="flex items-center gap-3">
        <button
          onClick={() => onPlay(!playing)}
          className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-ember text-ink transition hover:brightness-110 active:scale-95"
          aria-label={playing ? 'Pause' : 'Play the next 48 hours'}
        >
          {playing ? <Pause size={18} /> : <Play size={18} className="ml-0.5" />}
        </button>
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between gap-2">
            <div className="truncate font-display text-base font-semibold sm:text-lg">
              {relativeDay(iso, nowIso)}, {istTime(iso)}
              <span className="ml-2 text-xs font-medium text-mist/70">IST</span>
            </div>
            <div className="shrink-0 text-xs text-mist/80">
              {isNow ? (
                <span className="rounded-full bg-ember/20 px-2 py-0.5 font-semibold text-ember">Now</span>
              ) : isFuture ? (
                `+${frame - meta.now_frame} h forecast`
              ) : (
                `${meta.now_frame - frame} h ago`
              )}
            </div>
          </div>
          <div className="relative mt-5">
            <span className="pointer-events-none absolute -top-4 -translate-x-1/2 text-[10px] font-semibold text-ember" style={{ left: pct(meta.now_frame) }}>
              now
            </span>
            <input
              type="range"
              className="scrub"
              min={0}
              max={n - 1}
              value={frame}
              onChange={(e) => {
                onPlay(false)
                onFrame(Number(e.target.value))
              }}
              aria-label="Forecast hour"
            />
            <div className="pointer-events-none absolute inset-x-0 top-[22px] h-4 text-[10px] text-mist/70">
              {ticks.map((t) => (
                <span key={t.at} className="absolute -translate-x-1/2 whitespace-nowrap" style={{ left: pct(t.at) }}>
                  <span className="mx-auto block h-1.5 w-px bg-mist/40" />
                  {t.label}
                </span>
              ))}
            </div>
          </div>
          <div className="mt-7 flex items-center justify-between text-[11px] text-mist/70">
            <span>{assumed ? 'Assumes the fields seen burning in the last 24 h burn again at the same hours.' : 'Smoke from fires detected by satellite in the last 48 h.'}</span>
            {!isNow && (
              <button onClick={() => onFrame(meta.now_frame)} className="ml-3 inline-flex shrink-0 items-center gap-1 text-ember hover:underline">
                <RotateCcw size={11} /> back to now
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
