import type { Impact } from '../../types'
import { CardHeader } from '../CardHeader'
import { BASELINE, STATUS } from '../../lib/colors'
import { num } from '../../lib/format'

export function impactValue(impact: Impact, which: 'baseline' | 'predicted'): string {
  const v = impact[which]
  if (v === null) return impact.key === 'endurance_h' ? 'sustainable' : '—'
  const digits = impact.unit === 'A' ? 2 : 1
  const sep = impact.unit === '%' ? '' : ' '
  return `${num(v, digits)}${sep}${impact.unit}`
}

const EFFECT_COLOR = { worse: STATUS.serious, better: STATUS.good, neutral: BASELINE } as const

export function ImpactChain({ impacts }: { impacts: Impact[] }) {
  const changed = impacts.filter((i) => i.direction !== 'flat')
  const unchanged = impacts.filter((i) => i.direction === 'flat')
  return (
    <section className="card">
      <CardHeader title="Predicted impact" icon="trend" meta={<span className="count-pill">vs baseline</span>} subtitle="Compared with doing nothing, from the same starting state" />
      {changed.length === 0 ? (
        <p className="muted">No measurable impact on the monitored parameters.</p>
      ) : (
        <ol className="impact-chain">
          {changed.map((i) => (
            <li key={i.key} className="impact" style={{ borderLeftColor: EFFECT_COLOR[i.effect] }}>
              <div className="impact-label">
                {i.label}{' '}
                <span className="impact-arrow" aria-label={i.direction === 'up' ? 'increases' : 'decreases'}>
                  {i.direction === 'up' ? '↑' : '↓'}
                </span>
              </div>
              <div className="impact-values">
                <span className="muted">{impactValue(i, 'baseline')}</span> → <strong>{impactValue(i, 'predicted')}</strong>
              </div>
              <div className="impact-effect" style={{ color: EFFECT_COLOR[i.effect], borderColor: EFFECT_COLOR[i.effect] }}>
                {i.effect}
              </div>
            </li>
          ))}
        </ol>
      )}
      {unchanged.length > 0 && (
        <p className="muted small">Unchanged: {unchanged.map((i) => i.label.toLowerCase()).join(', ')}.</p>
      )}
    </section>
  )
}
