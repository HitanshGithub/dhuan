import type { RunMeta } from '../api'

export default function Legend({ meta }: { meta: RunMeta }) {
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
    </div>
  )
}
