import { useState } from 'react'
import { api } from '../../api'
import type { Catalog, Fault } from '../../types'
import { CardHeader } from '../CardHeader'
import { Icon } from '../Icon'

export function FaultPanel({ catalog, faults }: { catalog: Catalog | null; faults: Fault[] }) {
  const kinds = catalog?.kinds.filter((k) => k.category !== 'mitigation') ?? []
  const [kind, setKind] = useState('solar_degradation')
  const [magnitude, setMagnitude] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const spec = kinds.find((k) => k.kind === kind)
  const value = magnitude ?? spec?.magnitude?.default ?? null

  async function run(action: () => Promise<unknown>) {
    setBusy(true)
    setError(null)
    try {
      await action()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card demo-card">
      <CardHeader
        title="Environment event"
        icon="flask"
        subtitle="Emulates something happening to the spacecraft so you can watch the twin detect it. Not a command."
        meta={<span className="tag">Demo only</span>}
      />
      <div className="form-row">
        <label className="field">
          <span>Event</span>
          <select
            value={kind}
            onChange={(e) => {
              setKind(e.target.value)
              setMagnitude(null)
            }}
          >
            {kinds.map((k) => (
              <option key={k.kind} value={k.kind}>
                {k.label}
              </option>
            ))}
          </select>
        </label>
        {spec?.magnitude && value !== null && (
          <label className="field">
            <span>
              {spec.magnitude.label}: {value} {spec.magnitude.unit}
            </span>
            <input
              type="range"
              min={spec.magnitude.min}
              max={spec.magnitude.max}
              step={1}
              value={value}
              onChange={(e) => setMagnitude(Number(e.target.value))}
            />
          </label>
        )}
      </div>
      <div className="button-row">
        <button
          className="button accent"
          disabled={busy || !spec}
          onClick={() =>
            run(() =>
              api.injectFault({
                kind,
                magnitude: spec?.magnitude ? value : null,
                duration_min: spec?.requires_duration ? spec.default_duration_min : null,
              }),
            )
          }
        >
          <Icon name="play" size={14} /> Inject event
        </button>
        <button className="button secondary" disabled={busy || faults.length === 0} onClick={() => run(api.clearFaults)}>
          Clear events
        </button>
      </div>
      {error && <p className="error small">{error}</p>}
      {faults.length > 0 && (
        <ul className="fault-list">
          {faults.map((f, i) => (
            <li key={i}>{f.label}</li>
          ))}
        </ul>
      )}
    </section>
  )
}
