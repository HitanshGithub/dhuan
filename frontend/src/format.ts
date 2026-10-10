import type { Band } from './api'

export const BAND_COLOR: Record<Band, string> = {
  clear: '#9ad0a0',
  light: '#f3d98b',
  moderate: '#f3a35a',
  heavy: '#e05a3a',
  severe: '#8b1e4b',
}

export const BAND_LABEL: Record<Band, string> = {
  clear: 'Clear',
  light: 'Light',
  moderate: 'Moderate',
  heavy: 'Heavy',
  severe: 'Severe',
}

const IST = 'Asia/Kolkata'

/** '3:30 pm' (forecast hours fall on UTC whole hours, which are half past the hour in IST) or '6 am' when exact. */
export function istTime(iso: string): string {
  const d = new Date(iso)
  const minutes = Number(d.toLocaleTimeString('en-IN', { minute: '2-digit', timeZone: IST }))
  const opts: Intl.DateTimeFormatOptions = minutes ? { hour: 'numeric', minute: '2-digit', hour12: true, timeZone: IST } : { hour: 'numeric', hour12: true, timeZone: IST }
  return d.toLocaleTimeString('en-IN', opts).replace(/\s+/g, ' ').toLowerCase()
}

/** True when `iso` falls on a different IST calendar day than `prevIso`. */
export function newIstDay(iso: string, prevIso: string): boolean {
  return istDay(iso) !== istDay(prevIso)
}

export function istDay(iso: string): string {
  return new Date(iso).toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short', timeZone: IST })
}

export function istFull(iso: string): string {
  return `${istDay(iso)}, ${istTime(iso)}`
}

export function relativeDay(iso: string, nowIso: string): string {
  const d = new Date(iso)
  const n = new Date(nowIso)
  const dayOf = (x: Date) => new Date(x.toLocaleDateString('en-US', { timeZone: IST })).getTime()
  const diff = Math.round((dayOf(d) - dayOf(n)) / 86_400_000)
  if (diff === 0) return 'Today'
  if (diff === 1) return 'Tomorrow'
  if (diff === -1) return 'Yesterday'
  return istDay(iso)
}

export function formatCount(n: number): string {
  return n.toLocaleString('en-IN')
}
