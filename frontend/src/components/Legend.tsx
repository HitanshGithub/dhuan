import type { RunMeta } from '../api'

interface Props {
  meta: RunMeta
  showStations: boolean
  onToggleStations: () => void
}

export default function Legend({ meta, showStations, onToggleStations }: Props) {
  return (
    <div className="glass rounded-xl px-3 py-2 text-[11px] text-mist">
      <div className="mb-1 font-semibold text-white/90">Smoke from farm fires</div>
      <div className="flex items-center gap-1">
        {meta.bands.map((b) => (
          <div key={b.key} className="flex flex-col items-center" title={b.meaning}>
            <span className="h-2.5 w-9 rounded-sm" style={{ background: b.color }} />
            <span className="mt-0.5">{b.label}</span>
          </div>
        ))}
      </div>
      <div className="mt-1 text-[10px] text-mist/60">estimated extra PM2.5 · µg/m³ · from {meta.bands[1].from_ug}</div>
      {meta.has_stations && (
        <button onClick={onToggleStations} className="mt-2 flex w-full items-center justify-between gap-2 rounded-lg bg-white/5 px-2 py-1 text-left hover:bg-white/10">
          <span>
            <span className="mr-1.5 inline-block h-2 w-2 rounded-full border border-white/70 bg-[#e0433d] align-middle" />
            Measured AQI at stations (CPCB via WAQI)
          </span>
          <span className={`rounded-full px-1.5 py-px text-[10px] font-semibold ${showStations ? 'bg-emerald-400/20 text-emerald-200' : 'bg-white/10 text-mist'}`}>{showStations ? 'on' : 'off'}</span>
        </button>
      )}
    </div>
  )
}
