/** Mission clock: minutes → "T+HH:MM". */
export function missionTime(minutes: number): string {
  const total = Math.max(0, Math.floor(minutes))
  const h = Math.floor(total / 60)
  const m = total % 60
  return `T+${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
}

/** Duration: minutes → "34 min" / "4 h 12 min". */
export function duration(minutes: number): string {
  const total = Math.round(minutes)
  if (total < 60) return `${total} min`
  const h = Math.floor(total / 60)
  const m = total % 60
  return m === 0 ? `${h} h` : `${h} h ${m} min`
}

/** Relative axis tick: minutes → "0", "1h", "1h30". */
export function relTick(minutes: number): string {
  const total = Math.round(minutes)
  if (total === 0) return '0'
  const h = Math.floor(total / 60)
  const m = total % 60
  if (h === 0) return `${m}m`
  return m === 0 ? `${h}h` : `${h}h${String(m).padStart(2, '0')}`
}

export function num(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return value.toFixed(digits)
}

export function withUnit(value: number | null | undefined, unit: string, digits = 1): string {
  if (value === null || value === undefined) return '—'
  const sep = unit === '%' || unit === '' ? '' : ' '
  return `${num(value, digits)}${sep}${unit}`
}

export function signed(value: number, digits = 1): string {
  const s = value.toFixed(digits)
  return value > 0 ? `+${s}` : s
}

export function pct(value: number): string {
  return `${Math.round(value * 100)}%`
}
