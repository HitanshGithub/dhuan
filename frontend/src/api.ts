// Talks to the Dhuan API. In development Vite proxies /api and /data to the local backend.

export const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, '') ?? ''

export type Band = 'clear' | 'light' | 'moderate' | 'heavy' | 'severe'

export interface BandInfo {
  from_ug: number
  key: Band
  label: string
  color: string
  meaning: string
}

export interface RunMeta {
  run_id: string
  generated_at: string
  times: string[]
  now_frame: number
  bounds: [number, number][]
  fires: { count: number; assumed_repeat: number; by_state: Record<string, number>; window: string }
  parcels: number
  frame_max_ug: number[]
  bands: BandInfo[]
  data_url: string
  sources: Record<string, string | null>
  has_stations?: boolean
  replay?: { date: string; title: string } | null
  exposure?: {
    frames: { heavy: number; moderate: number }[]
    next_24h: { frame: number; heavy: number; moderate: number; districts: { name: string; ug: number }[] }
    thresholds: { moderate: number; heavy: number }
  }
}

export interface Replay {
  run_id: string
  date: string
  title: string
  fires: number
}

export interface Observed {
  name: string
  aqi: number
  pm25: number | null
  time: string | null
  distance_km: number
  category: string
  color: string
}

export interface Frame {
  time: string
  ist: string
  ug: number
  band: Band
  is_now: boolean
}

export interface Moment {
  frame: number
  time: string
  ist: string
  ug?: number
  key?: Band
  label?: string
  color?: string
  meaning?: string
}

export interface PointForecast {
  lat: number
  lon: number
  run_id: string
  generated_at: string
  now: { time: string; ist: string; ug: number; key: Band; label: string; color: string; meaning: string }
  arrival: Moment | null
  peak: Required<Moment>
  clears: Moment | null
  sources: { district: string; share: number }[]
  observed: Observed | null
  replay?: { date: string; title: string } | null
  frames: Frame[]
  fires: RunMeta['fires']
  disclaimer: string
}

export interface Advisory {
  subject: string
  body: string
  language: 'en' | 'hi' | 'pa'
  generated_by: 'template' | 'ai'
}

export interface Place {
  name: string
  lat: number
  lon: number
}

async function json<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init)
  if (!res.ok) {
    let detail = res.statusText
    try {
      detail = (await res.json()).detail ?? detail
    } catch {
      /* not json */
    }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

const runParam = (run?: string) => (run ? `&run=${encodeURIComponent(run)}` : '')

export const api = {
  latest: () => json<RunMeta>(`${API_BASE}/api/latest`),
  replays: () => json<Replay[]>(`${API_BASE}/api/replays`).catch(() => [] as Replay[]),
  // a replay's metadata comes straight from the data store; `base` is the live run's data_url minus its /runs/<id>
  runMeta: async (base: string, runId: string): Promise<RunMeta> => {
    const meta = await json<RunMeta>(`${base}/runs/${runId}/meta.json`)
    return { ...meta, data_url: `${base}/runs/${runId}` }
  },
  forecast: (lat: number, lon: number, run?: string) => json<PointForecast>(`${API_BASE}/api/forecast?lat=${lat}&lon=${lon}${runParam(run)}`),
  advisory: (lat: number, lon: number, lang: string, label: string, run?: string) =>
    json<Advisory>(`${API_BASE}/api/advisory?lat=${lat}&lon=${lon}&lang=${lang}&label=${encodeURIComponent(label)}${runParam(run)}`),
  subscribe: (body: { email: string; lat: number; lon: number; label: string; language: string }) =>
    json<{ id: string; status: string; note: string }>(`${API_BASE}/api/subscribe`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  preview: (id: string) =>
    json<{ sent: boolean; status?: string; subject?: string; body?: string; reason?: string }>(`${API_BASE}/api/subscribe/${id}/preview`, { method: 'POST' }),
}

export function dataUrl(meta: RunMeta, path: string): string {
  const base = meta.data_url.startsWith('http') ? meta.data_url : `${API_BASE}${meta.data_url}`
  return `${base}/${path}`
}

/** The root of the data store (CloudFront when deployed, the local /data mount in development). */
export function dataRoot(meta: RunMeta): string {
  const full = meta.data_url.startsWith('http') ? meta.data_url : `${API_BASE}${meta.data_url}`
  return full.replace(/\/runs\/[^/]+$/, '')
}

export function frameImage(meta: RunMeta, frame: number): string {
  return dataUrl(meta, `img/${String(frame).padStart(2, '0')}.png`)
}

// A name for a tapped point, from OpenStreetMap's Nominatim (light use, attributed in the About panel).
export async function reverseName(lat: number, lon: number): Promise<string | null> {
  try {
    const res = await fetch(`https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lon}&format=jsonv2&zoom=12&accept-language=en`)
    if (!res.ok) return null
    const a = ((await res.json()) as { address?: Record<string, string> }).address ?? {}
    const local = a.suburb ?? a.town ?? a.city ?? a.village ?? a.county ?? a.state_district
    const region = a.state ?? a.country
    if (!local) return region ?? null
    return region && region !== local ? `${local}, ${region}` : local
  } catch {
    return null
  }
}

// Open-Meteo's geocoder: free, no key, good coverage of Indian towns.
export async function geocode(q: string): Promise<Place[]> {
  if (q.trim().length < 2) return []
  const url = `https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(q)}&count=6&language=en&format=json&countryCode=IN`
  const res = await fetch(url)
  if (!res.ok) return []
  const data = (await res.json()) as { results?: { name: string; admin1?: string; latitude: number; longitude: number }[] }
  return (data.results ?? []).map((r) => ({ name: r.admin1 ? `${r.name}, ${r.admin1}` : r.name, lat: r.latitude, lon: r.longitude }))
}
