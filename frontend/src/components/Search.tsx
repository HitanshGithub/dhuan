import { LocateFixed, Search as SearchIcon, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { geocode, type Place } from '../api'

const QUICK: Place[] = [
  { name: 'Delhi', lat: 28.64, lon: 77.22 },
  { name: 'Chandigarh', lat: 30.73, lon: 76.78 },
  { name: 'Ludhiana', lat: 30.9, lon: 75.85 },
  { name: 'Lucknow', lat: 26.85, lon: 80.95 },
  { name: 'Jaipur', lat: 26.91, lon: 75.79 },
]

interface Props {
  onPlace: (p: Place) => void
  compact?: boolean
}

export default function Search({ onPlace, compact }: Props) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState<Place[]>([])
  const [open, setOpen] = useState(false)
  const [locating, setLocating] = useState(false)
  const timer = useRef<number | undefined>(undefined)

  useEffect(() => {
    window.clearTimeout(timer.current)
    if (q.trim().length < 2) {
      setResults([])
      return
    }
    timer.current = window.setTimeout(async () => {
      setResults(await geocode(q))
      setOpen(true)
    }, 250)
    return () => window.clearTimeout(timer.current)
  }, [q])

  const choose = (p: Place) => {
    onPlace(p)
    setQ('')
    setResults([])
    setOpen(false)
  }

  const locate = () => {
    if (!navigator.geolocation) return
    setLocating(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocating(false)
        choose({ name: 'My location', lat: pos.coords.latitude, lon: pos.coords.longitude })
      },
      () => setLocating(false),
      { enableHighAccuracy: false, timeout: 8000 },
    )
  }

  return (
    <div className="relative">
      <div className="flex items-center gap-2 rounded-xl bg-ink/60 px-3 py-2 ring-1 ring-line focus-within:ring-ember/70">
        <SearchIcon size={16} className="shrink-0 text-mist/70" />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onFocus={() => results.length && setOpen(true)}
          onBlur={() => window.setTimeout(() => setOpen(false), 150)}
          placeholder={compact ? 'Your town or school' : 'Search your town, school or colony'}
          className="w-full bg-transparent text-sm outline-none placeholder:text-mist/50"
          aria-label="Search for a place"
        />
        {q && (
          <button onClick={() => setQ('')} aria-label="Clear" className="text-mist/60 hover:text-white">
            <X size={14} />
          </button>
        )}
        <button onClick={locate} title="Use my location" aria-label="Use my location" className={`shrink-0 text-mist/70 hover:text-ember ${locating ? 'animate-pulse text-ember' : ''}`}>
          <LocateFixed size={16} />
        </button>
      </div>
      {open && results.length > 0 && (
        <ul className="glass absolute z-20 mt-1 w-full overflow-hidden rounded-xl text-sm shadow-xl">
          {results.map((r) => (
            <li key={`${r.lat},${r.lon}`}>
              <button onMouseDown={() => choose(r)} className="block w-full px-3 py-2 text-left hover:bg-white/5">
                {r.name}
              </button>
            </li>
          ))}
        </ul>
      )}
      {!compact && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {QUICK.map((p) => (
            <button key={p.name} onClick={() => choose(p)} className="rounded-full bg-white/5 px-2.5 py-1 text-xs text-mist ring-1 ring-line hover:bg-white/10 hover:text-white">
              {p.name}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
